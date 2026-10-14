"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_all_orders():
    """View all customer orders (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view all orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("All Orders")

        print("\n🔍 Filter by:")
        print("1. All orders")
        print("2. Pending orders")
        print("3. Processing orders")
        print("4. Ready for pickup")
        print("5. Completed orders")
        print("6. Cancelled orders")

        filter_choice = input("\nSelect filter (1-6): ").strip()

        status_filters = {
            '1': None,
            '2': 'pending',
            '3': 'processing',
            '4': 'ready',
            '5': 'completed',
            '6': 'cancelled'
        }

        status_filter = status_filters.get(filter_choice)

        with get_connection() as conn:
            if status_filter:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, total_amount,
                           order_status, order_date, pickup_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_status = ?
                    ORDER BY order_date DESC
                    LIMIT 50
                ''', (status_filter,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, total_amount,
                           order_status, order_date, pickup_date
                    FROM orders
                    WHERE source_type = 'butcher'
                    ORDER BY order_date DESC
                    LIMIT 50
                ''')

            orders = cursor.fetchall()

            if not orders:
                print("\n❌ No orders found")
            else:
                print(f"\n📋 ORDERS ({len(orders)} shown):")
                print("=" * 80)

                for order in orders:
                    order_id, order_num, user_name, amount, status, order_date, pickup_date = order

                    status_icons = {
                        'pending': '⏳',
                        'processing': '🔄',
                        'ready': '✅',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }
                    icon = status_icons.get(status, '❓')

                    print(f"\n{icon} {order_num}")
                    print(f"   Customer: {user_name}")
                    print(f"   Amount: {format_currency(float(amount))}")
                    print(f"   Status: {status.upper()}")
                    print(f"   Ordered: {format_date(order_date)}")
                    if pickup_date:
                        print(f"   Pickup: {pickup_date}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing all orders: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")
