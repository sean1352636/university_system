"""Charity Shop - Sales mixin for CharityShopApp."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui._imports import (
    messagebox, datetime,
    FINANCE_INTEGRATION_AVAILABLE, ACTIVITY_LOGGER_AVAILABLE, EMAIL_SERVICE_AVAILABLE,
    get_current_user, get_student_info,
    send_email, log_activity, logger,
    load_email_template, render_email_template,
)
from education_system.systems.university.plugins.campus_commerce.domain.charity_shop.services.charity_shop_service import (
    sell_item as sell_item_service,
)


class SalesMixin:
    """Sales operations for CharityShopApp."""

    def sell_item(self):
        """Mark selected item as sold with payment processing and email receipt."""
        from education_system.systems.university.plugins.campus_commerce.interfaces.gui.charity_shop_gui.dialogs import SellDialog

        item = self.get_selected_item()
        if not item:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.sales.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.please_select_an_item_to_sell', default="Please select an item to sell."))
            return

        if item["quantity"] <= 0:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.sales.dialogs.no_stock', default="No Stock"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.this_item_is_out_of_stock', default="This item is out of stock."))
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

            # The domain service writes the sale and posts it to Finance
            # (Finance Account debit, or revenue for cash/card) exactly once.
            current_user = get_current_user()
            processed_by = current_user.get('username', 'System') if current_user else "System"
            sale = sell_item_service(
                item_id=item["id"],
                quantity=quantity,
                payment_method=payment_method,
                student_id=student_id,
                processed_by=processed_by,
            )
            if not sale.get('success'):
                if payment_method == "Finance Account":
                    messagebox.showerror(_t('gui.shell.services.charity_shop_gui.sales.dialogs.payment_failed', default="Payment Failed"), f"Finance Account payment failed: {sale.get('message', '')}")
                else:
                    messagebox.showerror(_t('gui.shell.services.charity_shop_gui.sales.dialogs.error', default="Error"), sale.get('message', 'Sale failed'))
                return
            transaction_ref = sale['transaction_ref']

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

            messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.sales.dialogs.sale_complete', default="Sale Complete"), success_msg)

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
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.sales.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.please_select_an_item', default="Please select an item."))
            return

        if item["status"] == "Available":
            messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.sales.dialogs.info', default="Info"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.item_is_already_marked_as_available', default="Item is already marked as available."))
            return

        if messagebox.askyesno(_t('gui.shell.services.charity_shop_gui.sales.dialogs.confirm', default="Confirm"), f"Mark '{item['name']}' as available?"):
            self.db.mark_as_available(item["id"])
            self.refresh_stock_list()
            messagebox.showinfo(_t('gui.shell.services.charity_shop_gui.sales.dialogs.success', default="Success"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.item_marked_as_available', default="Item marked as available!"))

    def adjust_quantity(self, delta: int):
        """Quickly adjust quantity of selected item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning(_t('gui.shell.services.charity_shop_gui.sales.dialogs.no_selection', default="No Selection"), _t('gui.shell.services.charity_shop_gui.sales.dialogs.please_select_an_item_to_adjust_quantity', default="Please select an item to adjust quantity."))
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
