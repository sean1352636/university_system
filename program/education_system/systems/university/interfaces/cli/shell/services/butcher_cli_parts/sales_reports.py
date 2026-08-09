"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def sales_reports():
    """Generate sales reports (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view reports")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Sales Reports")

        print("\n📊 Report Period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Date Range")

        choice = input("\nSelect period (1-4): ").strip()

        now = datetime.now()

        if choice == '1':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "Today"
        elif choice == '2':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "This Week"
        elif choice == '3':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "This Month"
        elif choice == '4':
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()

            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                period_name = f"{start_str} to {end_str}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Total sales
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount), AVG(total_amount)
                FROM orders
                WHERE source_type = 'butcher' AND order_date >= ? AND order_date <= ?
                AND order_status != 'cancelled'
            ''', (start_date.isoformat(), end_date.isoformat()))

            stats = cursor.fetchone()
            total_orders, total_revenue, avg_order = stats if stats else (0, 0, 0)

            # Sales by category
            category_cursor = conn.execute('''
                SELECT p.category, SUM(oi.subtotal), SUM(oi.quantity_kg)
                FROM order_items oi
                JOIN products p ON oi.product_id = p.source_product_id AND p.source_type = 'butcher'
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_date <= ?
                AND o.order_status != 'cancelled'
                GROUP BY p.category
                ORDER BY SUM(oi.subtotal) DESC
            ''', (start_date.isoformat(), end_date.isoformat()))

            category_sales = category_cursor.fetchall()

            # Top products
            product_cursor = conn.execute('''
                SELECT oi.item_name as product_name, SUM(oi.quantity_kg), SUM(oi.subtotal), COUNT(*)
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_date <= ?
                AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY SUM(oi.subtotal) DESC
                LIMIT 10
            ''', (start_date.isoformat(), end_date.isoformat()))

            top_products = product_cursor.fetchall()

            # Display report
            print("\n" + "=" * 80)
            print(f"           SALES REPORT - {period_name}")
            print("=" * 80)

            print("\n📊 OVERVIEW:")
            print(f"   Total Orders: {total_orders or 0}")
            print(f"   Total Revenue: {format_currency(float(total_revenue or 0))}")
            print(f"   Average Order: {format_currency(float(avg_order or 0))}")

            if category_sales:
                print("\n📦 SALES BY CATEGORY:")
                print("-" * 80)
                for category, revenue, quantity in category_sales:
                    print(f"   {category}: {format_currency(float(revenue))} ({float(quantity):.2f}kg)")

            if top_products:
                print("\n🏆 TOP PRODUCTS:")
                print("-" * 80)
                for idx, (name, quantity, revenue, count) in enumerate(top_products, 1):
                    print(f"   {idx}. {name}")
                    print(f"      Revenue: {format_currency(float(revenue))} | Sold: {float(quantity):.2f}kg | Orders: {count}")

            print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error generating sales report: {e}")
        print(f"❌ Error generating report: {e}")

    input("\nPress Enter to continue...")
