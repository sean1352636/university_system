"""CartTabMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class CartTabMixin:
    def build_cart_tab(self):
        """Build the shopping cart tab."""
        # Header
        header = tk.Label(
            self.cart_tab,
            text="🛒 Your Shopping Cart",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        # Cart items area
        self.cart_items_frame = tk.Frame(
            self.cart_tab, bg=self.colors["card"], relief="sunken", bd=2
        )
        self.cart_items_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Summary panel at the bottom
        summary_frame = tk.Frame(self.cart_tab, bg=self.colors["primary"])
        summary_frame.pack(fill="x", padx=20, pady=10)

        self.subtotal_label = tk.Label(
            summary_frame,
            text="Subtotal: £0.00",
            font=("Arial", 12),
            bg=self.colors["primary"],
            fg="white",
        )
        self.subtotal_label.pack(side="left", padx=20, pady=10)

        self.discount_label = tk.Label(
            summary_frame,
            text="Discount: £0.00",
            font=("Arial", 12),
            bg=self.colors["primary"],
            fg="white",
        )
        self.discount_label.pack(side="left", padx=20, pady=10)

        self.total_label = tk.Label(
            summary_frame,
            text="Total: £0.00",
            font=("Arial", 14, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["accent"],
        )
        self.total_label.pack(side="left", padx=20, pady=10)

        checkout_btn = tk.Button(
            summary_frame,
            text="💳 Checkout",
            font=("Arial", 12, "bold"),
            bg=self.colors["success"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.checkout,
        )
        checkout_btn.pack(side="right", padx=20, pady=10)

        clear_btn = tk.Button(
            summary_frame,
            text="🗑️ Clear",
            font=("Arial", 12, "bold"),
            bg=self.colors["danger"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.clear_cart,
        )
        clear_btn.pack(side="right", padx=5, pady=10)

        # Secondary actions row: save-for-later, restore, schedule, recurring
        actions_row = tk.Frame(self.cart_tab, bg=self.colors["background"])
        actions_row.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(actions_row, text="💾 Save for Later",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._cart_save_action).pack(side="left", padx=4)
        tk.Button(actions_row, text="↩ Restore Saved",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=12, pady=6,
                  command=self._cart_restore_action).pack(side="left", padx=4)
        tk.Button(actions_row, text="📅 Schedule Pre-Order",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._open_preorder_dialog).pack(side="left", padx=4)
        tk.Button(actions_row, text="🔁 Make Standing Order",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._open_new_recurring_dialog
                  ).pack(side="left", padx=4)

        self.refresh_cart()

    def _cart_save_action(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to save your cart for later.")
            return
        if not self.cart:
            messagebox.showinfo("Empty Cart", "Nothing to save.")
            return
        if self.save_cart_for_later():
            messagebox.showinfo("Saved",
                                "Your cart has been saved. Come back any time.")

    def _cart_restore_action(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to restore your saved cart.")
            return
        if not self.has_saved_cart():
            messagebox.showinfo("Nothing saved",
                                "You don't have a saved cart.")
            return
        if self.restore_saved_cart():
            self.clear_saved_cart()
            self.refresh_cart()
            self.update_cart_tab_title()
            self.refresh_products()
            self.set_status("Saved cart restored.")

    def refresh_cart(self):
        """Repaint the cart contents and update totals."""
        if not getattr(self, "cart_tab", None) or not getattr(self.cart_tab, "_lazy_built", False):
            return
        for widget in self.cart_items_frame.winfo_children():
            widget.destroy()

        if not self.cart:
            tk.Label(
                self.cart_items_frame,
                text="Your cart is empty 🛒\nGo to the Shop tab to add some delicious treats!",
                font=("Arial", 14, "italic"),
                bg=self.colors["card"],
                fg=self.colors["text"],
            ).pack(expand=True, pady=50)
            self.update_cart_totals()
            return

        # Column headers
        headers_frame = tk.Frame(self.cart_items_frame, bg=self.colors["secondary"])
        headers_frame.pack(fill="x")

        for text, width in [("Item", 30), ("Price", 12), ("Quantity", 18), ("Subtotal", 12), ("", 10)]:
            tk.Label(
                headers_frame,
                text=text,
                font=("Arial", 11, "bold"),
                bg=self.colors["secondary"],
                fg="white",
                width=width,
                anchor="w",
                padx=5,
                pady=8,
            ).pack(side="left")

        # Item rows
        for item_name, qty in list(self.cart.items()):
            self.create_cart_row(item_name, qty)

        self.update_cart_totals()

    def create_cart_row(self, item_name, qty):
        """Create one row in the cart for a given item."""
        # Look up the price from the catalog
        price = 0
        emoji = ""
        for category in self.products.values():
            if item_name in category:
                price = category[item_name]["price"]
                emoji = category[item_name]["emoji"]
                break

        row = tk.Frame(self.cart_items_frame, bg=self.colors["card"])
        row.pack(fill="x", pady=2)

        tk.Label(
            row,
            text=f"{emoji} {item_name}",
            font=("Arial", 11),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=30,
            anchor="w",
            padx=5,
            pady=8,
        ).pack(side="left")

        tk.Label(
            row,
            text=f"£{price:.2f}",
            font=("Arial", 11),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=12,
            anchor="w",
        ).pack(side="left")

        # Quantity controls
        qty_frame = tk.Frame(row, bg=self.colors["card"], width=120)
        qty_frame.pack(side="left", padx=20)

        tk.Button(
            qty_frame,
            text="-",
            font=("Arial", 10, "bold"),
            bg=self.colors["secondary"],
            fg="white",
            width=2,
            relief="flat",
            cursor="hand2",
            command=lambda: self.update_cart_qty(item_name, -1),
        ).pack(side="left", padx=2)

        tk.Label(
            qty_frame,
            text=str(qty),
            font=("Arial", 11, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=4,
        ).pack(side="left")

        tk.Button(
            qty_frame,
            text="+",
            font=("Arial", 10, "bold"),
            bg=self.colors["secondary"],
            fg="white",
            width=2,
            relief="flat",
            cursor="hand2",
            command=lambda: self.update_cart_qty(item_name, 1),
        ).pack(side="left", padx=2)

        tk.Label(
            row,
            text=f"£{price * qty:.2f}",
            font=("Arial", 11, "bold"),
            bg=self.colors["card"],
            fg=self.colors["secondary"],
            width=12,
            anchor="w",
        ).pack(side="left", padx=10)

        tk.Button(
            row,
            text="✕",
            font=("Arial", 10, "bold"),
            bg=self.colors["danger"],
            fg="white",
            relief="flat",
            cursor="hand2",
            width=3,
            command=lambda: self.remove_from_cart(item_name),
        ).pack(side="left", padx=5)

    def add_to_cart(self, item_name):
        """Add one unit of an item to the cart, respecting stock."""
        # Get stock for this item
        stock = 0
        for category in self.products.values():
            if item_name in category:
                stock = category[item_name]["stock"]
                break

        current_qty = self.cart.get(item_name, 0)
        if current_qty >= stock:
            messagebox.showwarning("Stock Limit", f"Only {stock} units of {item_name} available!")
            return

        self.cart[item_name] = current_qty + 1
        self.refresh_cart()
        self.update_cart_tab_title()
        self.set_status(f"Added {item_name} to cart!")

    def update_cart_qty(self, item_name, change):
        """Increase or decrease the quantity of an item in the cart."""
        if item_name not in self.cart:
            return

        new_qty = self.cart[item_name] + change

        if new_qty <= 0:
            del self.cart[item_name]
        else:
            # Check stock limit
            stock = 0
            for category in self.products.values():
                if item_name in category:
                    stock = category[item_name]["stock"]
                    break
            if new_qty > stock:
                messagebox.showwarning("Stock Limit", f"Only {stock} units available!")
                return
            self.cart[item_name] = new_qty

        self.refresh_cart()
        self.update_cart_tab_title()

    def remove_from_cart(self, item_name):
        """Remove an item entirely from the cart."""
        if item_name in self.cart:
            del self.cart[item_name]
            self.refresh_cart()
            self.update_cart_tab_title()
            self.set_status(f"Removed {item_name} from cart")

    def clear_cart(self):
        """Empty the cart after confirmation."""
        if not self.cart:
            return
        if messagebox.askyesno("Clear Cart", "Are you sure you want to clear the cart?"):
            self.cart.clear()
            self.refresh_cart()
            self.update_cart_tab_title()
            self.set_status("Cart cleared")

    def update_cart_tab_title(self):
        """Reflect the cart item count in the sidebar Cart button label."""
        count = sum(self.cart.values())
        btn = getattr(self, "_panel_buttons", {}).get("cart")
        if btn is not None:
            try:
                btn.configure(text=f"🛒  Cart ({count})")
            except tk.TclError:
                pass
        self.update_cart_totals()

    def update_cart_totals(self):
        """Recompute subtotal, discount, and total."""
        if not getattr(self, "cart_tab", None) or not getattr(self.cart_tab, "_lazy_built", False):
            return
        subtotal = 0
        for item_name, qty in self.cart.items():
            for category in self.products.values():
                if item_name in category:
                    subtotal += category[item_name]["price"] * qty
                    break

        # Discount based on user type
        discount_rate = 0
        if self.user_type == "Student":
            discount_rate = 0.10  # 10% off
        elif self.user_type == "Staff":
            discount_rate = 0.15  # 15% off

        discount = subtotal * discount_rate
        total = subtotal - discount

        self.subtotal_label.config(text=f"Subtotal: {self.fmt_money(subtotal)}")
        self.discount_label.config(
            text=f"Discount ({self.user_type}): {self.fmt_money(discount)}"
        )
        self.total_label.config(text=f"Total: {self.fmt_money(total)}")

