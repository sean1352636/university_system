"""Charity Shop - Basket operations mixin for CharityShopApp."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui._imports import (
    messagebox, datetime,
    FINANCE_INTEGRATION_AVAILABLE, ACTIVITY_LOGGER_AVAILABLE, EMAIL_SERVICE_AVAILABLE,
    get_current_user, get_student_info,
    send_email, log_activity, logger,
    load_email_template, render_email_template,
)
from education_system.systems.university.plugins.campus_commerce.domain.charity_shop.services.charity_shop_service import (
    checkout_basket as checkout_basket_service,
)


class BasketOpsMixin:
    """Basket operations for CharityShopApp."""

    def show_basket_window(self):
        """Show the basket window."""
        from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui.basket import BasketWindow

        if self.basket_window is None or not self.basket_window.winfo_exists():
            self.basket_window = BasketWindow(self.root, self)
        else:
            self.basket_window.lift()
            self.basket_window.focus_set()

    def add_to_basket(self):
        """Add selected item to the shopping basket."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.please_select_an_item_to_add_to_basket', default="Please select an item to add to basket."))
            return

        if item["quantity"] <= 0:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.out_of_stock', default="Out of Stock"), _t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.this_item_is_out_of_stock', default="This item is out of stock."))
            return

        if item["status"] == "Sold":
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.not_available', default="Not Available"), _t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.this_item_has_been_sold', default="This item has been sold."))
            return

        # Check if item is already in basket
        for basket_item in self.basket:
            if basket_item['id'] == item['id']:
                # Check if we can add more
                if basket_item['quantity'] >= item['quantity']:
                    messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.limit_reached', default="Limit Reached"), f"Maximum available quantity ({item['quantity']}) already in basket.")
                    return
                basket_item['quantity'] += 1
                self.update_basket_window()
                messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.added', default="Added"), f"Added another '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")
                return

        # Add new item to basket
        self.basket.append({
            'id': item['id'],
            'name': item['name'],
            'price': item['price'],
            'quantity': 1,
            'max_qty': item['quantity']
        })
        self.update_basket_window()
        messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.added_to_basket', default="Added to Basket"), f"Added '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")

    def remove_from_basket(self, index: int):
        """Remove item at specified index from basket."""
        if 0 <= index < len(self.basket):
            self.basket.pop(index)
            self.update_basket_window()

    def clear_basket(self):
        """Clear all items from basket."""
        self.basket = []
        self.update_basket_window()

    def update_basket_window(self):
        """Update the basket window if it's open."""
        if self.basket_window is not None and self.basket_window.winfo_exists():
            self.basket_window.refresh_display()

    def checkout(self):
        """Open checkout dialog to complete purchase."""
        from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui.dialogs import CheckoutDialog

        if not self.basket:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.empty_basket', default="Empty Basket"), _t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.please_add_items_to_basket_before_checkout', default="Please add items to basket before checkout."))
            return

        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in self.basket)

        # Open checkout dialog (pass current user for auto-fill)
        dialog = CheckoutDialog(self.root, self.basket, total, self.current_user)

        if dialog.result:
            self._process_checkout(dialog.result)

    def _process_checkout(self, checkout_data: dict):
        """Process the checkout and complete the sale."""
        payment_method = checkout_data['payment_method']
        student_id = checkout_data.get('student_id')
        customer_email = checkout_data.get('customer_email')
        total_amount = checkout_data['total']

        # The domain service saves the transaction, updates stock and posts to
        # Finance (Finance Account debit, or revenue for cash/card) exactly once.
        current_user = get_current_user()
        processed_by = current_user.get('username', 'System') if current_user else "System"
        sale = checkout_basket_service(
            items=self.basket,
            payment_method=payment_method,
            student_id=student_id,
            processed_by=processed_by,
        )
        if not sale.get('success'):
            if payment_method == "Finance Account":
                messagebox.showerror(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.payment_failed', default="Payment Failed"), f"Finance Account payment failed: {sale.get('message', '')}")
            else:
                messagebox.showerror(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.error', default="Error"), sale.get('message', 'Checkout failed'))
            return
        transaction_ref = sale['transaction_ref']

        items_sold = [{
            'name': basket_item['name'],
            'quantity': basket_item['quantity'],
            'price': basket_item['price'],
            'subtotal': basket_item['price'] * basket_item['quantity']
        } for basket_item in self.basket]

        # Send email receipt if email provided
        receipt_sent = False
        if customer_email and EMAIL_SERVICE_AVAILABLE:
            receipt_sent = self._send_basket_receipt(
                customer_email=customer_email,
                items=items_sold,
                total_amount=total_amount,
                payment_method=payment_method,
                transaction_ref=transaction_ref,
                student_id=student_id
            )

        # Clear basket and refresh
        self.basket = []
        self.update_basket_window()
        self.refresh_stock_list()

        # Show success message
        success_msg = "Purchase Complete!\n\n"
        success_msg += f"Items: {len(items_sold)}\n"
        success_msg += f"Total: \u00a3{total_amount:.2f}\n"
        success_msg += f"Payment: {payment_method}"
        if receipt_sent:
            success_msg += f"\n\nReceipt sent to {customer_email}"
        elif customer_email and not receipt_sent:
            success_msg += "\n\n(Receipt email could not be sent)"

        messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.basket_ops.dialogs.checkout_complete', default="Checkout Complete"), success_msg)

        # Log activity
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('checkout', 'charity_shop_basket', details={
                'items_count': len(items_sold),
                'total_revenue': total_amount,
                'payment_method': payment_method,
                'student_id': student_id,
                'transaction_ref': transaction_ref,
                'receipt_sent': receipt_sent
            })

    def _send_basket_receipt(self, customer_email: str, items: list, total_amount: float,
                             payment_method: str, transaction_ref: str, student_id: str = None) -> bool:
        """Send basket purchase receipt email to customer using JSON template."""
        try:
            # Get customer name if available
            customer_name = "Valued Customer"
            if student_id and FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_name = student_info.get('full_name', customer_name)

            # Build items list for receipt
            items_text = ""
            for item in items:
                items_text += f"  {item['name']:<25} x{item['quantity']:<3} \u00a3{item['price']:.2f}  =  \u00a3{item['subtotal']:.2f}\n"

            # Load template from JSON file
            template = load_email_template("charity_shop_basket_receipt")

            if not template:
                logger.error("Failed to load charity_shop_basket_receipt template")
                return False

            # Prepare template variables
            variables = {
                'customer_name': customer_name,
                'transaction_ref': transaction_ref,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method': payment_method,
                'items_list': items_text,
                'total_amount': f"{total_amount:.2f}"
            }

            # Render the template
            subject, body = render_email_template(template, variables)

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Basket receipt sent to {customer_email} for transaction {transaction_ref}")
                return True
            else:
                logger.warning(f"Failed to send basket receipt to {customer_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending basket receipt: {e}")
            return False
