"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_order_receipt():
    """View detailed receipt for a specific order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in")
        input("\nPress Enter to continue...")
        return

    try:
        order_number = input("\nEnter order number: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            return

        with get_connection() as conn:
            # Check if user owns this order or is admin
            if is_admin():
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, user_email, total_amount,
                           order_status, order_date, pickup_date, payment_method, notes, completed_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ?
                ''', (order_number,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, user_email, total_amount,
                           order_status, order_date, pickup_date, payment_method, notes, completed_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ? AND user_id = ?
                ''', (order_number, user.get('username')))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found or access denied")
                return

            (order_id, order_num, user_name, user_email, total, status,
             order_date, pickup_date, payment_method, notes, completed_date) = order

            # Print receipt
            print("\n" + "=" * 80)
            print("                    UNIVERSITY BUTCHER SHOP")
            print("                         ORDER RECEIPT")
            print("=" * 80)
            print(f"\nOrder Number: {order_num}")
            print(f"Date: {format_date(order_date)}")
            print(f"Customer: {user_name}")
            if user_email:
                print(f"Email: {user_email}")
            print(f"\nStatus: {status.upper()}")
            if pickup_date:
                print(f"Pickup Date: {pickup_date}")
            if completed_date:
                print(f"Completed: {format_date(completed_date)}")

            print("\n" + "-" * 80)
            print(f"{'Item':<30} {'Qty (kg)':<12} {'Price/kg':<12} {'Subtotal':>10}")
            print("-" * 80)

            # Get items
            item_cursor = conn.execute('''
                SELECT item_name as product_name, quantity_kg, unit_price, subtotal
                FROM order_items
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (order_id,))
            items = item_cursor.fetchall()

            for item in items:
                prod_name, qty, price, subtotal = item
                print(f"{prod_name:<30} {float(qty):<12.2f} {format_currency(float(price)):<12} {format_currency(float(subtotal)):>10}")

            print("-" * 80)
            print(f"{'TOTAL':<54} {format_currency(float(total)):>10}")
            print("-" * 80)
            print(f"\nPayment Method: {payment_method.replace('_', ' ').title()}")

            if notes:
                print(f"\nNotes: {notes}")

            print("\n" + "=" * 80)
            print("                    Thank you for your order!")
            print("=" * 80)

    except Exception as e:
        logger.error(f"Error viewing receipt: {e}")
        print(f"❌ Error viewing receipt: {e}")
