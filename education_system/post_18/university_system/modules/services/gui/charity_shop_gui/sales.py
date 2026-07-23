"""Charity Shop - Sales mixin for CharityShopApp."""

from education_system.post_18.university_system.modules.services.gui.charity_shop_gui._imports import (
    messagebox, datetime,
    FINANCE_INTEGRATION_AVAILABLE, ACTIVITY_LOGGER_AVAILABLE, EMAIL_SERVICE_AVAILABLE,
    get_current_user, get_student_info,
    record_revenue_to_finance, process_student_finance_account_payment,
    send_email, log_activity, logger,
    load_email_template, render_email_template,
)


class SalesMixin:
    """Sales operations for CharityShopApp."""

    def sell_item(self):
        """Mark selected item as sold with payment processing and email receipt."""
        from education_system.post_18.university_system.modules.services.gui.charity_shop_gui.dialogs import SellDialog

        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to sell.")
            return

        if item["quantity"] <= 0:
            messagebox.showwarning("No Stock", "This item is out of stock.")
            return

        # Open enhanced sell dialog with payment options (pass current user for auto-fill)
        dialog = SellDialog(self.root, item["name"], item["quantity"], item["price"], self.current_user)

        if dialog.result:
            sale_data = dialog.result
            quantity = sale_data['quantity']
            total_amount = sale_data['total']
            payment_method = sale_data['payment_method']
            student_id = sale_data['student_id']
            customer_email = sale_data['customer_email']

            # Generate transaction reference
            transaction_ref = f"CS-{item['id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Process payment based on method
            payment_success = True
            payment_message = ""

            if payment_method == "Finance Account":
                # Process payment from student finance account
                if FINANCE_INTEGRATION_AVAILABLE and student_id:
                    current_user = get_current_user()
                    processed_by = current_user.get('username', 'System') if current_user else "System"
                    result = process_student_finance_account_payment(
                        student_id=student_id,
                        amount=total_amount,
                        description=f"Charity Shop: {quantity}x {item['name']}",
                        transaction_source="Charity Shop",
                        transaction_ref=transaction_ref,
                        processed_by=processed_by
                    )
                    payment_success = result.get('success', False)
                    payment_message = result.get('message', '')

                    if not payment_success:
                        messagebox.showerror("Payment Failed", f"Finance Account payment failed: {payment_message}")
                        return
                else:
                    messagebox.showerror("Error", "Finance integration not available for student account payment")
                    return

            # Mark item as sold in database
            self.db.mark_as_sold(item["id"], quantity)

            # Record revenue to central finance system
            if FINANCE_INTEGRATION_AVAILABLE:
                record_revenue_to_finance(
                    student_id=student_id or "WALK-IN",
                    amount=total_amount,
                    revenue_category="Charity Shop Sale",
                    transaction_source="Charity Shop",
                    transaction_ref=transaction_ref,
                    payment_method=payment_method,
                    notes=f"{quantity}x {item['name']}"
                )

            # Send email receipt if email provided
            receipt_sent = False
            if customer_email and EMAIL_SERVICE_AVAILABLE:
                receipt_sent = self._send_purchase_receipt(
                    customer_email=customer_email,
                    item_name=item['name'],
                    quantity=quantity,
                    unit_price=item['price'],
                    total_amount=total_amount,
                    payment_method=payment_method,
                    transaction_ref=transaction_ref,
                    student_id=student_id
                )

            self.refresh_stock_list()

            # Show success message
            success_msg = f"Sold {quantity} x {item['name']}!\n"
            success_msg += f"Total: \u00a3{total_amount:.2f}\n"
            success_msg += f"Payment: {payment_method}"
            if receipt_sent:
                success_msg += f"\n\nReceipt sent to {customer_email}"
            elif customer_email and not receipt_sent:
                success_msg += "\n\n(Receipt email could not be sent)"

            messagebox.showinfo("Sale Complete", success_msg)

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('sell', 'charity_shop_item', details={
                    'item_id': item["id"],
                    'name': item["name"],
                    'quantity_sold': quantity,
                    'price_per_item': item["price"],
                    'total_revenue': total_amount,
                    'payment_method': payment_method,
                    'student_id': student_id,
                    'transaction_ref': transaction_ref,
                    'receipt_sent': receipt_sent
                })

    def _send_purchase_receipt(self, customer_email: str, item_name: str, quantity: int,
                               unit_price: float, total_amount: float, payment_method: str,
                               transaction_ref: str, student_id: str = None) -> bool:
        """Send purchase receipt email to customer using JSON template."""
        try:
            # Get student name if available
            customer_name = "Valued Customer"
            if student_id and FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_name = student_info.get('full_name', customer_name)

            # Load template from JSON file
            template = load_email_template("charity_shop_single_item_receipt")

            if not template:
                logger.error("Failed to load charity_shop_single_item_receipt template")
                return False

            # Prepare template variables
            variables = {
                'customer_name': customer_name,
                'transaction_ref': transaction_ref,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method': payment_method,
                'item_name': item_name,
                'quantity': quantity,
                'unit_price': f"{unit_price:.2f}",
                'total_amount': f"{total_amount:.2f}"
            }

            # Render the template
            subject, body = render_email_template(template, variables)

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Purchase receipt sent to {customer_email} for transaction {transaction_ref}")
                return True
            else:
                logger.warning(f"Failed to send receipt to {customer_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending purchase receipt: {e}")
            return False

    def mark_available(self):
        """Mark selected item as available (not sold)."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item.")
            return

        if item["status"] == "Available":
            messagebox.showinfo("Info", "Item is already marked as available.")
            return

        if messagebox.askyesno("Confirm", f"Mark '{item['name']}' as available?"):
            self.db.mark_as_available(item["id"])
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item marked as available!")

    def adjust_quantity(self, delta: int):
        """Quickly adjust quantity of selected item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to adjust quantity.")
            return

        # Get full item data
        all_items = self.db.get_all_stock()
        item_data = None
        for db_item in all_items:
            if db_item[0] == item["id"]:
                item_data = db_item
                break

        if item_data:
            new_quantity = max(0, item["quantity"] + delta)
            sold = item_data[7] if len(item_data) > 7 else 0
            sold_qty = item_data[9] if len(item_data) > 9 else 0
            self.db.update_item(
                item["id"], item["name"], item["category"],
                item["price"], new_quantity, item["condition"],
                bool(sold), sold_qty
            )
            self.refresh_stock_list()
