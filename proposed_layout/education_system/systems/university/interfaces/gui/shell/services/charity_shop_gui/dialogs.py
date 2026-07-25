"""Charity Shop - Dialog windows (ItemDialog, SellDialog, CheckoutDialog)."""

from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui._imports import (
    tk, ttk, messagebox,
    FINANCE_INTEGRATION_AVAILABLE,
    get_student_finance_account_balance, get_student_email,
    _t,
)


class ItemDialog(tk.Toplevel):
    """Dialog for adding/editing stock items."""

    CATEGORIES = [
        "Books", "Clothing", "Electronics", "Furniture", "Homeware",
        "Toys", "Music/DVDs", "Accessories", "Sports", "Other"
    ]

    CONDITIONS = ["New", "Excellent", "Good", "Fair", "Poor"]

    def __init__(self, parent, title: str, item_data: tuple = None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.item_data = item_data

        self.transient(parent)

        self.geometry("400x420")
        self.resizable(False, False)

        self.create_widgets()

        if item_data:
            self.populate_fields(item_data)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        # Wait for window to be visible before grabbing focus
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(main_frame, text=_t("charity_shop.labels.item_name")).grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Category
        ttk.Label(main_frame, text=_t("charity_shop.labels.category")).grid(row=1, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(main_frame, textvariable=self.category_var,
                                           values=self.CATEGORIES, width=32, state="readonly")
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set(self.CATEGORIES[0])

        # Price
        ttk.Label(main_frame, text=_t("charity_shop.labels.price")).grid(row=2, column=0, sticky="w", pady=5)
        self.price_var = tk.StringVar()
        self.price_entry = ttk.Entry(main_frame, textvariable=self.price_var, width=35)
        self.price_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Quantity
        ttk.Label(main_frame, text=_t("charity_shop.labels.quantity")).grid(row=3, column=0, sticky="w", pady=5)
        self.quantity_var = tk.StringVar(value="1")
        self.quantity_spinbox = ttk.Spinbox(main_frame, textvariable=self.quantity_var,
                                            from_=0, to=9999, width=33)
        self.quantity_spinbox.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Condition
        ttk.Label(main_frame, text=_t("charity_shop.labels.condition")).grid(row=4, column=0, sticky="w", pady=5)
        self.condition_var = tk.StringVar()
        self.condition_combo = ttk.Combobox(main_frame, textvariable=self.condition_var,
                                            values=self.CONDITIONS, width=32, state="readonly")
        self.condition_combo.grid(row=4, column=1, pady=5, padx=(10, 0))
        self.condition_combo.set("Good")

        # Sold Status
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky="w", pady=5)
        self.sold_var = tk.BooleanVar(value=False)
        self.sold_check = ttk.Checkbutton(main_frame, text="Mark as Sold", variable=self.sold_var)
        self.sold_check.grid(row=5, column=1, pady=5, padx=(10, 0), sticky="w")

        # Sold Quantity
        ttk.Label(main_frame, text="Qty Sold:").grid(row=6, column=0, sticky="w", pady=5)
        self.sold_qty_var = tk.StringVar(value="0")
        self.sold_qty_spinbox = ttk.Spinbox(main_frame, textvariable=self.sold_qty_var,
                                             from_=0, to=9999, width=33)
        self.sold_qty_spinbox.grid(row=6, column=1, pady=5, padx=(10, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=30)

        ttk.Button(button_frame, text="Save", command=self.save, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=12).pack(side=tk.LEFT, padx=5)

        self.name_entry.focus_set()

    def populate_fields(self, item_data):
        """Populate fields with existing item data."""
        # item_data: (id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity)
        self.name_var.set(item_data[1])
        self.category_var.set(item_data[2])
        self.price_var.set(f"{item_data[3]:.2f}")
        self.quantity_var.set(str(item_data[4]))
        self.condition_var.set(item_data[5])
        self.sold_var.set(bool(item_data[7]) if len(item_data) > 7 else False)
        self.sold_qty_var.set(str(item_data[9]) if len(item_data) > 9 and item_data[9] else "0")

    def validate(self):
        """Validate input fields."""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Please enter an item name.", parent=self)
            return False

        try:
            price = float(self.price_var.get())
            if price < 0:
                raise ValueError("Price must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid price.", parent=self)
            return False

        try:
            quantity = int(self.quantity_var.get())
            if quantity < 0:
                raise ValueError("Quantity must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid quantity.", parent=self)
            return False

        try:
            sold_qty = int(self.sold_qty_var.get())
            if sold_qty < 0:
                raise ValueError("Sold quantity must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid sold quantity.", parent=self)
            return False

        return True

    def save(self):
        """Save and close dialog."""
        if self.validate():
            self.result = {
                "name": self.name_var.get().strip(),
                "category": self.category_var.get(),
                "price": float(self.price_var.get()),
                "quantity": int(self.quantity_var.get()),
                "condition": self.condition_var.get(),
                "sold": self.sold_var.get(),
                "sold_quantity": int(self.sold_qty_var.get())
            }
            self.destroy()

    def cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()


class SellDialog(tk.Toplevel):
    """Dialog for selling items with payment method selection."""

    PAYMENT_METHODS = ["Cash", "Debit/Credit Card", "Finance Account"]

    def __init__(self, parent, item_name: str, max_quantity: int, unit_price: float, current_user: dict = None):
        super().__init__(parent)
        self.title("Sell Item")
        self.result = None
        self.max_quantity = max_quantity
        self.unit_price = unit_price
        self.item_name = item_name
        self.current_user = current_user

        self.transient(parent)

        self.geometry("450x420")
        self.resizable(False, False)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        # Wait for window to be visible before grabbing focus
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Item info header
        ttk.Label(main_frame, text=f"Selling: {self.item_name}", font=("Helvetica", 12, "bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text=f"Price: \u00a3{self.unit_price:.2f} each | Available: {self.max_quantity}").pack(pady=(0, 15))

        # Quantity selection
        qty_frame = ttk.LabelFrame(main_frame, text="Quantity", padding="10")
        qty_frame.pack(fill=tk.X, pady=5)

        qty_inner = ttk.Frame(qty_frame)
        qty_inner.pack()

        ttk.Label(qty_inner, text="Quantity to sell:").pack(side=tk.LEFT)
        self.qty_var = tk.StringVar(value="1")
        self.qty_spinbox = ttk.Spinbox(qty_inner, textvariable=self.qty_var,
                                        from_=1, to=self.max_quantity, width=10,
                                        command=self.update_total)
        self.qty_spinbox.pack(side=tk.LEFT, padx=10)
        self.qty_spinbox.bind('<KeyRelease>', lambda e: self.update_total())

        # Total display
        self.total_label = ttk.Label(qty_frame, text=f"Total: \u00a3{self.unit_price:.2f}", font=("Helvetica", 11, "bold"))
        self.total_label.pack(pady=5)

        # Customer info - display current logged-in user (read-only)
        customer_frame = ttk.LabelFrame(main_frame, text="Customer (Logged-in User)", padding="10")
        customer_frame.pack(fill=tk.X, pady=10)

        # Get current user details
        self.user_id = ""
        self.user_email = ""
        self.user_name = "Guest"
        if self.current_user:
            self.user_id = self.current_user.get('student_id') or self.current_user.get('username', '')
            self.user_email = self.current_user.get('email', '')
            first_name = self.current_user.get('first_name', '')
            last_name = self.current_user.get('last_name', '')
            self.user_name = f"{first_name} {last_name}".strip() or self.current_user.get('username', 'Guest')

            # If no email in current_user, try to fetch from database
            if not self.user_email and self.user_id and FINANCE_INTEGRATION_AVAILABLE:
                self.user_email = get_student_email(self.user_id) or ""

        # Display user info (read-only)
        ttk.Label(customer_frame, text=f"Name: {self.user_name}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(customer_frame, text=f"ID: {self.user_id}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(customer_frame, text=f"Email: {self.user_email or '(not set)'}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)

        # Balance display
        self.balance_label = ttk.Label(customer_frame, text="", foreground="blue", font=("Helvetica", 10, "bold"))
        self.balance_label.pack(anchor=tk.W, pady=5)

        # Auto-lookup balance
        if self.user_id:
            self.after(100, self._load_balance)

        # Payment method
        payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="10")
        payment_frame.pack(fill=tk.X, pady=10)

        self.payment_var = tk.StringVar(value="Cash")
        for method in self.PAYMENT_METHODS:
            ttk.Radiobutton(payment_frame, text=method, variable=self.payment_var, value=method).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text="Complete Sale", command=self.sell, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Sell All", command=self.sell_all, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=10).pack(side=tk.LEFT, padx=5)

    def update_total(self):
        """Update the total price display."""
        try:
            qty = int(self.qty_var.get())
            total = qty * self.unit_price
            self.total_label.config(text=f"Total: \u00a3{total:.2f}")
        except ValueError:
            self.total_label.config(text=f"Total: \u00a3{self.unit_price:.2f}")

    def _load_balance(self):
        """Load the current user's finance account balance."""
        if not self.user_id or not FINANCE_INTEGRATION_AVAILABLE:
            return

        balance = get_student_finance_account_balance(self.user_id)
        if balance is not None:
            color = "green" if balance >= self.unit_price else "red"
            self.balance_label.config(text=f"Finance Balance: \u00a3{balance:.2f}", foreground=color)
        else:
            self.balance_label.config(text="No finance account", foreground="orange")

    def validate_sale(self) -> bool:
        """Validate the sale before processing."""
        try:
            qty = int(self.qty_var.get())
            if qty < 1 or qty > self.max_quantity:
                messagebox.showerror("Error", f"Quantity must be between 1 and {self.max_quantity}", parent=self)
                return False
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid quantity", parent=self)
            return False

        # If paying with Finance Account, verify user has balance
        if self.payment_var.get() == "Finance Account":
            if not self.user_id:
                messagebox.showerror("Error", "You must be logged in to use Finance Account payment", parent=self)
                return False

            if FINANCE_INTEGRATION_AVAILABLE:
                balance = get_student_finance_account_balance(self.user_id)
                total = qty * self.unit_price
                if balance is None:
                    messagebox.showerror("Error", "You do not have a finance account", parent=self)
                    return False
                if balance < total:
                    messagebox.showerror("Error", f"Insufficient balance. Current: \u00a3{balance:.2f}, Required: \u00a3{total:.2f}", parent=self)
                    return False

        return True

    def sell(self):
        """Complete the sale with specified quantity."""
        if not self.validate_sale():
            return

        qty = int(self.qty_var.get())
        total = qty * self.unit_price

        self.result = {
            'quantity': qty,
            'total': total,
            'payment_method': self.payment_var.get(),
            'student_id': self.user_id or None,
            'customer_email': self.user_email or None
        }
        self.destroy()

    def sell_all(self):
        """Sell all available quantity."""
        self.qty_var.set(str(self.max_quantity))
        self.update_total()
        self.sell()

    def cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()


class CheckoutDialog(tk.Toplevel):
    """Dialog for checkout with payment method selection."""

    PAYMENT_METHODS = ["Cash", "Debit/Credit Card", "Finance Account"]

    def __init__(self, parent, basket: list, total: float, current_user: dict = None):
        super().__init__(parent)
        self.title("Checkout")
        self.result = None
        self.basket = basket
        self.total = total
        self.current_user = current_user

        self.transient(parent)
        self.geometry("600x700")
        self.minsize(550, 600)
        self.resizable(True, True)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create checkout dialog widgets."""
        # Create canvas with scrollbar for the entire content
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text="Checkout", font=("Helvetica", 16, "bold")).pack(pady=(0, 20))

        # Order summary
        summary_frame = ttk.LabelFrame(main_frame, text="Order Summary", padding="15")
        summary_frame.pack(fill=tk.X, pady=(0, 15))

        # Items header
        header_frame = ttk.Frame(summary_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Item", font=("Helvetica", 10, "bold"), width=25).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Qty", font=("Helvetica", 10, "bold"), width=6).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Subtotal", font=("Helvetica", 10, "bold"), width=10).pack(side=tk.RIGHT)

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # Items list
        items_frame = ttk.Frame(summary_frame)
        items_frame.pack(fill=tk.X, pady=5)

        for item in self.basket:
            subtotal = item['price'] * item['quantity']
            item_row = ttk.Frame(items_frame)
            item_row.pack(fill=tk.X, pady=2)
            ttk.Label(item_row, text=item['name'][:28], width=28, anchor="w").pack(side=tk.LEFT)
            ttk.Label(item_row, text=f"x{item['quantity']}", width=6).pack(side=tk.LEFT)
            ttk.Label(item_row, text=f"\u00a3{subtotal:.2f}", width=10, anchor="e").pack(side=tk.RIGHT)

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Total
        total_frame = ttk.Frame(summary_frame)
        total_frame.pack(fill=tk.X, pady=5)
        ttk.Label(total_frame, text="TOTAL:", font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(total_frame, text=f"\u00a3{self.total:.2f}", font=("Helvetica", 16, "bold"), foreground="green").pack(side=tk.RIGHT)

        # Customer info - display current logged-in user (read-only)
        customer_frame = ttk.LabelFrame(main_frame, text="Customer (Logged-in User)", padding="15")
        customer_frame.pack(fill=tk.X, pady=15)

        # Get current user details
        self.user_id = ""
        self.user_email = ""
        self.user_name = "Guest"
        if self.current_user:
            self.user_id = self.current_user.get('student_id') or self.current_user.get('username', '')
            self.user_email = self.current_user.get('email', '')
            first_name = self.current_user.get('first_name', '')
            last_name = self.current_user.get('last_name', '')
            self.user_name = f"{first_name} {last_name}".strip() or self.current_user.get('username', 'Guest')

            # If no email in current_user, try to fetch from database
            if not self.user_email and self.user_id and FINANCE_INTEGRATION_AVAILABLE:
                self.user_email = get_student_email(self.user_id) or ""

        # Display user info (read-only)
        ttk.Label(customer_frame, text=f"Name: {self.user_name}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)
        ttk.Label(customer_frame, text=f"ID: {self.user_id}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)
        ttk.Label(customer_frame, text=f"Email: {self.user_email or '(not set)'}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)

        # Balance display
        self.balance_label = ttk.Label(customer_frame, text="", foreground="blue", font=("Helvetica", 11, "bold"))
        self.balance_label.pack(anchor=tk.W, pady=8)

        # Auto-lookup balance
        if self.user_id:
            self.after(100, self._load_balance)

        # Payment method
        payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="15")
        payment_frame.pack(fill=tk.X, pady=15)

        self.payment_var = tk.StringVar(value="Cash")
        for method in self.PAYMENT_METHODS:
            rb = ttk.Radiobutton(payment_frame, text=method, variable=self.payment_var, value=method)
            rb.pack(anchor=tk.W, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Complete Purchase", command=self.complete_purchase, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=12).pack(side=tk.LEFT, padx=5)

    def _load_balance(self):
        """Load the current user's finance account balance."""
        if not self.user_id or not FINANCE_INTEGRATION_AVAILABLE:
            return

        balance = get_student_finance_account_balance(self.user_id)
        if balance is not None:
            color = "green" if balance >= self.total else "red"
            self.balance_label.config(text=f"Finance Balance: \u00a3{balance:.2f}", foreground=color)
        else:
            self.balance_label.config(text="No finance account", foreground="orange")

    def validate_checkout(self) -> bool:
        """Validate checkout before processing."""
        if self.payment_var.get() == "Finance Account":
            if not self.user_id:
                messagebox.showerror("Error", "You must be logged in to use Finance Account payment", parent=self)
                return False

            if FINANCE_INTEGRATION_AVAILABLE:
                balance = get_student_finance_account_balance(self.user_id)
                if balance is None:
                    messagebox.showerror("Error", "You do not have a finance account", parent=self)
                    return False
                if balance < self.total:
                    messagebox.showerror("Error", f"Insufficient balance. Current: \u00a3{balance:.2f}, Required: \u00a3{self.total:.2f}", parent=self)
                    return False

        return True

    def complete_purchase(self):
        """Complete the purchase."""
        if not self.validate_checkout():
            return

        self.result = {
            'total': self.total,
            'payment_method': self.payment_var.get(),
            'student_id': self.user_id or None,
            'customer_email': self.user_email or None
        }
        self.destroy()

    def cancel(self):
        """Cancel checkout."""
        self.result = None
        self.destroy()
