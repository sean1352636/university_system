"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def popular_products_analysis():
    """Analyze popular products (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view analytics")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Popular Products Analysis")

        days = input("\nAnalyze last (days, default 30): ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        with get_connection() as conn:
            # Most ordered products
            cursor = conn.execute('''
                SELECT oi.item_name as product_name,
                       COUNT(DISTINCT o.order_id) as order_count,
                       SUM(oi.quantity_kg) as total_quantity,
                       SUM(oi.subtotal) as total_revenue,
                       AVG(oi.quantity_kg) as avg_quantity_per_order
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY order_count DESC
                LIMIT 15
            ''', (start_date,))

            products = cursor.fetchall()

            print(f"\n🏆 MOST POPULAR PRODUCTS (Last {days} days):")
            print("=" * 80)

            if not products:
                print("No orders in this period")
            else:
                print(f"\n{'Rank':<6} {'Product':<25} {'Orders':<10} {'Qty (kg)':<12} {'Revenue':>15}")
                print("-" * 80)

                for idx, (name, orders, quantity, revenue, avg_qty) in enumerate(products, 1):
                    print(f"{idx:<6} {name:<25} {orders:<10} {float(quantity):<12.2f} {format_currency(float(revenue)):>15}")

                print("=" * 80)

                # Additional insights
                total_orders = sum(p[1] for p in products)
                total_revenue = sum(p[3] for p in products)

                print("\n📊 INSIGHTS:")
                print("   Top 15 products account for:")
                print(f"   • {total_orders} orders")
                print(f"   • {format_currency(float(total_revenue))} revenue")

    except Exception as e:
        logger.error(f"Error analyzing popular products: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")
