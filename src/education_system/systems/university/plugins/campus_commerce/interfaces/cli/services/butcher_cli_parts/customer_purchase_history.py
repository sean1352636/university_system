"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def customer_purchase_history():
    """View customer purchase history (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view customer data")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Customer Purchase History")

        customer_id = input("\nEnter customer username: ").strip()

        if not customer_id:
            print("❌ Customer username cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Customer summary
            summary_cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount), AVG(total_amount),
                       MIN(order_date), MAX(order_date)
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ? AND order_status != 'cancelled'
            ''', (customer_id,))

            summary = summary_cursor.fetchone()

            if not summary or summary[0] == 0:
                print(f"\n❌ No orders found for customer: {customer_id}")
                input("\nPress Enter to continue...")
                return

            total_orders, total_spent, avg_order, first_order, last_order = summary

            # Favorite products
            fav_cursor = conn.execute('''
                SELECT oi.item_name as product_name, COUNT(*), SUM(oi.quantity_kg), SUM(oi.subtotal)
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.user_id = ? AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            ''', (customer_id,))

            favorites = fav_cursor.fetchall()

            # Recent orders
            recent_cursor = conn.execute('''
                SELECT order_number, total_amount, order_status, order_date
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ?
                ORDER BY order_date DESC
                LIMIT 10
            ''', (customer_id,))

            recent_orders = recent_cursor.fetchall()

            # Display report
            print("\n" + "=" * 80)
            print(f"        CUSTOMER PURCHASE HISTORY - {customer_id}")
            print("=" * 80)

            print("\n📊 SUMMARY:")
            print(f"   Total Orders: {total_orders}")
            print(f"   Total Spent: {format_currency(float(total_spent))}")
            print(f"   Average Order: {format_currency(float(avg_order))}")
            print(f"   First Order: {format_date(first_order)}")
            print(f"   Last Order: {format_date(last_order)}")

            if favorites:
                print("\n🏆 FAVORITE PRODUCTS:")
                print("-" * 80)
                for idx, (name, count, quantity, spent) in enumerate(favorites, 1):
                    print(f"   {idx}. {name}")
                    print(f"      Ordered {count} times | {float(quantity):.2f}kg total | {format_currency(float(spent))}")

            if recent_orders:
                print("\n📜 RECENT ORDERS:")
                print("-" * 80)
                for order_num, amount, status, order_date in recent_orders:
                    status_icons = {
                        'pending': '⏳',
                        'processing': '🔄',
                        'ready': '✅',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }
                    icon = status_icons.get(status, '❓')
                    print(f"   {icon} {order_num} - {format_currency(float(amount))} - {status} - {format_date(order_date)}")

            print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing customer history: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")
