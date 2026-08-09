"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_my_orders():
    """View user's order history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("My Orders")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT order_id, order_number, total_amount, order_status,
                       order_date, pickup_date, payment_method, notes
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ?
                ORDER BY order_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            orders = cursor.fetchall()

            if not orders:
                print("\n❌ No orders found")
            else:
                print(f"\n📜 YOUR ORDERS ({len(orders)} total):")

                for order in orders:
                    try:
                        (order_id, order_num, total, status, order_date,
                         pickup_date, payment_method, notes) = order

                        status_icons = {
                            'pending': '⏳',
                            'processing': '🔄',
                            'ready': '✅',
                            'completed': '✔️',
                            'cancelled': '❌'
                        }
                        status_icon = status_icons.get(status, '❓')

                        print(f"\n{'-' * 80}")
                        print(f"{status_icon} Order: {order_num}")
                        print(f"   Status: {status.upper()}")
                        print(f"   Total: {format_currency(float(total))}")
                        print(f"   Payment: {payment_method.replace('_', ' ').title()}")
                        print(f"   Ordered: {format_date(order_date)}")
                        if pickup_date:
                            print(f"   Pickup: {pickup_date}")
                        if notes:
                            print(f"   Notes: {notes}")

                        # Get order items
                        item_cursor = conn.execute('''
                            SELECT item_name as product_name, quantity_kg, unit_price, subtotal
                            FROM order_items
                            WHERE order_id = ? AND source_type = 'butcher'
                        ''', (order_id,))
                        items = item_cursor.fetchall()

                        if items:
                            print("   Items:")
                            for item in items:
                                prod_name, qty, price, subtotal = item
                                print(f"     • {prod_name}: {float(qty):.2f}kg @ {format_currency(float(price))}/kg = {format_currency(float(subtotal))}")

                    except Exception as e:
                        logger.error(f"Error displaying order: {e}")
                        continue

                # Option to view specific order or cancel
                print(f"\n{'-' * 80}")
                print("\nOptions:")
                print("1. View detailed receipt for an order")
                print("2. Cancel a pending order")
                print("0. Return to menu")

                choice = input("\nEnter choice: ").strip()

                if choice == '1':
                    view_order_receipt()
                elif choice == '2':
                    cancel_order()

    except Exception as e:
        logger.error(f"Error viewing orders: {e}")
        print(f"❌ Error viewing orders: {e}")

    input("\nPress Enter to continue...")
