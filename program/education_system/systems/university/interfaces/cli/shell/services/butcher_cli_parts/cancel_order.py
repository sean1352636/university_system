"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def cancel_order():
    """Cancel a pending order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in")
        input("\nPress Enter to continue...")
        return

    try:
        order_number = input("\nEnter order number to cancel: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            return

        with get_connection() as conn:
            # Check order exists and is pending
            if is_admin():
                cursor = conn.execute('''
                    SELECT order_id, total_amount, order_status, payment_method
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ?
                ''', (order_number,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, total_amount, order_status, payment_method
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ? AND user_id = ?
                ''', (order_number, user.get('username')))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found or access denied")
                return

            order_id, total, status, payment_method = order

            if status != 'pending':
                print(f"❌ Cannot cancel order with status: {status}")
                print("   Only pending orders can be cancelled")
                return

            confirm = input(f"\n⚠️  Cancel order {order_number} ({format_currency(float(total))})? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Cancellation aborted")
                return

            # Restore stock
            item_cursor = conn.execute('''
                SELECT product_id, quantity_kg
                FROM order_items
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (order_id,))
            items = item_cursor.fetchall()

            with transaction() as trans_conn:
                for product_id, quantity in items:
                    trans_conn.execute('''
                        UPDATE products
                        SET stock_kg = stock_kg + ?
                        WHERE source_product_id = ? AND source_type = 'butcher'
                    ''', (quantity, product_id))

                # Update order status
                trans_conn.execute('''
                    UPDATE orders
                    SET order_status = 'cancelled'
                    WHERE order_id = ? AND source_type = 'butcher'
                ''', (order_id,))

            # Refund if paid via finance account
            if payment_method == 'finance_account' and FINANCE_AVAILABLE:
                try:
                    record_payment_to_finance(
                        user.get('username'),
                        -float(total),  # Negative for refund
                        'refund',
                        'Butcher Shop',
                        f'Refund for {order_number}'
                    )
                except Exception as e:
                    logger.error(f"Error processing refund: {e}")

            print(f"\n✅ Order {order_number} has been cancelled")
            if payment_method == 'finance_account':
                print(f"   Refund of {format_currency(float(total))} processed to finance account")

            logger.info(f"User {user.get('username')} cancelled order {order_number}")

    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        print(f"❌ Error cancelling order: {e}")
