"""Charity Shop - Basket window."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui._imports import tk, ttk, messagebox


class BasketWindow(tk.Toplevel):
    """Separate window for viewing and managing the shopping basket."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app  # Reference to main CharityShopApp
        self.title(_t('gui.shell.services.charity_shop_gui.basket.windows.shopping_basket', default="Shopping Basket"))
        self.geometry("500x500")
        self.minsize(400, 400)

        self.create_widgets()
        self.refresh_display()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Create basket window widgets."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t('gui.shell.services.charity_shop_gui.basket.labels.shopping_basket', default="Shopping Basket"), font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)

        self.item_count_label = ttk.Label(header_frame, text=_t('gui.shell.services.charity_shop_gui.basket.labels.value_0_items', default="0 items"), foreground="gray")
        self.item_count_label.pack(side=tk.RIGHT)

        # Basket items treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("name", "qty", "price", "subtotal")
        self.basket_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        self.basket_tree.heading("name", text=_t('gui.shell.services.charity_shop_gui.basket.headings.item', default="Item"))
        self.basket_tree.heading("qty", text=_t('gui.shell.services.charity_shop_gui.basket.headings.qty', default="Qty"))
        self.basket_tree.heading("price", text=_t('gui.shell.services.charity_shop_gui.basket.headings.price', default="Price"))
        self.basket_tree.heading("subtotal", text=_t('gui.shell.services.charity_shop_gui.basket.headings.subtotal', default="Subtotal"))

        self.basket_tree.column("name", width=200, anchor="w")
        self.basket_tree.column("qty", width=60, anchor="center")
        self.basket_tree.column("price", width=80, anchor="e")
        self.basket_tree.column("subtotal", width=100, anchor="e")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.basket_tree.yview)
        self.basket_tree.configure(yscrollcommand=scrollbar.set)

        self.basket_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Quantity adjustment frame
        qty_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.services.charity_shop_gui.basket.labels.adjust_quantity', default="Adjust Quantity"), padding="10")
        qty_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(qty_frame, text="-1", command=self.decrease_qty, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(qty_frame, text="+1", command=self.increase_qty, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(qty_frame, text=_t('gui.shell.services.charity_shop_gui.basket.buttons.remove_item', default="Remove Item"), command=self.remove_selected, width=12).pack(side=tk.LEFT, padx=15)
        ttk.Button(qty_frame, text=_t('gui.shell.services.charity_shop_gui.basket.buttons.clear_all', default="Clear All"), command=self.clear_all, width=10).pack(side=tk.RIGHT, padx=5)

        # Total frame
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=10)

        ttk.Separator(total_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        total_inner = ttk.Frame(total_frame)
        total_inner.pack(fill=tk.X)

        ttk.Label(total_inner, text=_t('gui.shell.services.charity_shop_gui.basket.labels.total', default="Total:"), font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        self.total_label = ttk.Label(total_inner, text="\u00a30.00", font=("Helvetica", 16, "bold"), foreground="green")
        self.total_label.pack(side=tk.RIGHT)

        # Checkout button
        checkout_btn = ttk.Button(main_frame, text=_t('gui.shell.services.charity_shop_gui.basket.buttons.proceed_to_checkout', default="Proceed to Checkout"), command=self.proceed_to_checkout)
        checkout_btn.pack(fill=tk.X, pady=(10, 0))

        # Style the checkout button
        try:
            style = ttk.Style()
            style.configure("Checkout.TButton", font=("Helvetica", 12, "bold"))
            checkout_btn.configure(style="Checkout.TButton")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def refresh_display(self):
        """Refresh the basket display from app data."""
        # Clear existing items
        for item in self.basket_tree.get_children():
            self.basket_tree.delete(item)

        # Add basket items
        total = 0.0
        total_items = 0
        for basket_item in self.app.basket:
            subtotal = basket_item['price'] * basket_item['quantity']
            total += subtotal
            total_items += basket_item['quantity']

            self.basket_tree.insert("", tk.END, values=(
                basket_item['name'],
                basket_item['quantity'],
                f"\u00a3{basket_item['price']:.2f}",
                f"\u00a3{subtotal:.2f}"
            ))

        # Update totals
        self.total_label.config(text=f"\u00a3{total:.2f}")
        self.item_count_label.config(text=f"{total_items} item{'s' if total_items != 1 else ''}")

    def get_selected_index(self):
        """Get the index of the selected item."""
        selection = self.basket_tree.selection()
        if not selection:
            return None
        return self.basket_tree.index(selection[0])

    def decrease_qty(self):
        """Decrease quantity of selected item."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.please_select_an_item', default="Please select an item."), parent=self)
            return

        if self.app.basket[idx]['quantity'] > 1:
            self.app.basket[idx]['quantity'] -= 1
            self.refresh_display()
        else:
            # Remove if quantity would become 0
            if messagebox.askyesno(_t('gui.shell.services.charity_shop_gui.basket.dialogs.remove_item', default="Remove Item"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.remove_this_item_from_basket', default="Remove this item from basket?"), parent=self):
                self.app.remove_from_basket(idx)
                self.refresh_display()

    def increase_qty(self):
        """Increase quantity of selected item."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.please_select_an_item', default="Please select an item."), parent=self)
            return

        basket_item = self.app.basket[idx]
        if basket_item['quantity'] < basket_item['max_qty']:
            basket_item['quantity'] += 1
            self.refresh_display()
        else:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket.dialogs.limit_reached', default="Limit Reached"), f"Maximum available quantity ({basket_item['max_qty']}) reached.", parent=self)

    def remove_selected(self):
        """Remove selected item from basket."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.please_select_an_item_to_remove', default="Please select an item to remove."), parent=self)
            return

        item_name = self.app.basket[idx]['name']
        if messagebox.askyesno(_t('gui.shell.services.charity_shop_gui.basket.dialogs.confirm', default="Confirm"), f"Remove '{item_name}' from basket?", parent=self):
            self.app.remove_from_basket(idx)
            self.refresh_display()

    def clear_all(self):
        """Clear all items from basket."""
        if not self.app.basket:
            messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.basket.dialogs.empty', default="Empty"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.basket_is_already_empty', default="Basket is already empty."), parent=self)
            return

        if messagebox.askyesno(_t('gui.shell.services.charity_shop_gui.basket.dialogs.confirm', default="Confirm"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.clear_all_items_from_basket', default="Clear all items from basket?"), parent=self):
            self.app.clear_basket()
            self.refresh_display()

    def proceed_to_checkout(self):
        """Open checkout dialog."""
        if not self.app.basket:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket.dialogs.empty_basket', default="Empty Basket"), _t('gui.shell.services.charity_shop_gui.basket.dialogs.please_add_items_to_basket_before_checkout', default="Please add items to basket before checkout."), parent=self)
            return

        from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui.dialogs import CheckoutDialog

        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in self.app.basket)

        # Open checkout dialog (pass current user for auto-fill)
        dialog = CheckoutDialog(self, self.app.basket, total, self.app.current_user)

        if dialog.result:
            self.app._process_checkout(dialog.result)
            self.refresh_display()

    def on_close(self):
        """Handle window close."""
        self.app.basket_window = None
        self.destroy()
