"""Charity Shop - Basket operations mixin for CharityShopApp."""

from education_system.university_system.modules.services.gui.charity_shop_gui._imports import (
    messagebox, datetime, json, sqlite3,
    FINANCE_INTEGRATION_AVAILABLE, ACTIVITY_LOGGER_AVAILABLE, EMAIL_SERVICE_AVAILABLE,
    DEFAULT_DB_PATH,
    get_current_user, get_student_info,
    record_revenue_to_finance, process_student_finance_account_payment,
    send_email, log_activity, logger,
    load_email_template, render_email_template,
)


class BasketOpsMixin:
    """Basket operations for CharityShopApp."""

    def show_basket_window(self):
        """Show the basket window."""
        from education_system.university_system.modules.services.gui.charity_shop_gui.basket import BasketWindow

        if self.basket_window is None or not self.basket_window.winfo_exists():
            self.basket_window = BasketWindow(self.root, self)
        else:
            self.basket_window.lift()
            self.basket_window.focus_set()

    def add_to_basket(self):
        """Add selected item to the shopping basket."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to add to basket.")
            return

        if item["quantity"] <= 0:
            messagebox.showwarning("Out of Stock", "This item is out of stock.")
            return

        if item["status"] == "Sold":
            messagebox.showwarning("Not Available", "This item has been sold.")
            return

        # Check if item is already in basket
        for basket_item in self.basket:
            if basket_item['id'] == item['id']:
                # Check if we can add more
                if basket_item['quantity'] >= item['quantity']:
                    messagebox.showwarning("Limit Reached", f"Maximum available quantity ({item['quantity']}) already in basket.")
                    return
                basket_item['quantity'] += 1
                self.update_basket_window()
                messagebox.showinfo("Added", f"Added another '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")
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
        messagebox.showinfo("Added to Basket", f"Added '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")

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
        from education_system.university_system.modules.services.gui.charity_shop_gui.dialogs import CheckoutDialog

        if not self.basket:
            messagebox.showwarning("Empty Basket", "Please add items to basket before checkout.")
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

        # Generate transaction reference
        transaction_ref = f"CS-BASKET-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Process payment based on method
        if payment_method == "Finance Account":
            if FINANCE_INTEGRATION_AVAILABLE and student_id:
                current_user = get_current_user()
                processed_by = current_user.get('username', 'System') if current_user else "System"
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=total_amount,
                    description=f"Charity Shop: {len(self.basket)} items",
                    transaction_source="Charity Shop",
                    transaction_ref=transaction_ref,
                    processed_by=processed_by
                )
                if not result.get('success', False):
                    messagebox.showerror("Payment Failed", f"Finance Account payment failed: {result.get('message', '')}")
                    return
            else:
                messagebox.showerror("Error", "Finance integration not available for student account payment")
                return

        # Save transaction to database
        self._save_transaction(transaction_ref, student_id, total_amount, payment_method, self.basket)

        # Process each item in basket
        items_sold = []
        for basket_item in self.basket:
            self.db.mark_as_sold(basket_item['id'], basket_item['quantity'])
            items_sold.append({
                'name': basket_item['name'],
                'quantity': basket_item['quantity'],
                'price': basket_item['price'],
                'subtotal': basket_item['price'] * basket_item['quantity']
            })

        # Record revenue to central finance system
        if FINANCE_INTEGRATION_AVAILABLE:
            record_revenue_to_finance(
                student_id=student_id or "WALK-IN",
                amount=total_amount,
                revenue_category="Charity Shop Sale",
                transaction_source="Charity Shop",
                transaction_ref=transaction_ref,
                payment_method=payment_method,
                notes=f"Basket checkout: {len(items_sold)} items"
            )

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
        success_msg = f"Purchase Complete!\n\n"
        success_msg += f"Items: {len(items_sold)}\n"
        success_msg += f"Total: \u00a3{total_amount:.2f}\n"
        success_msg += f"Payment: {payment_method}"
        if receipt_sent:
            success_msg += f"\n\nReceipt sent to {customer_email}"
        elif customer_email and not receipt_sent:
            success_msg += f"\n\n(Receipt email could not be sent)"

        messagebox.showinfo("Checkout Complete", success_msg)

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

    def _save_transaction(self, transaction_ref, student_id, total_amount, payment_method, basket_items):
        """Save transaction to database for refund tracking"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Charity shop transactions now use unified 'transactions' table with source_type='charity_shop'

            # Convert basket items to JSON string
            items_json = json.dumps([{
                'id': item['id'],
                'name': item['name'],
                'quantity': item['quantity'],
                'price': item['price']
            } for item in basket_items])

            # Insert transaction
            cursor.execute('''
                INSERT INTO transactions
                (source_type, reference_number, customer_id, amount, payment_method, status, notes, created_at)
                VALUES ('charity_shop', ?, ?, ?, ?, 'completed', ?, ?)
            ''', (transaction_ref, student_id, total_amount, payment_method, items_json,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()
            logger.info(f"Transaction {transaction_ref} saved to database")

        except Exception as e:
            logger.error(f"Error saving transaction: {e}")
