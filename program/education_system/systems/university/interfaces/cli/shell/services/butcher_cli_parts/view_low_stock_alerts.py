"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_low_stock_alerts():
    """View products with low stock (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view alerts")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Low Stock Alerts")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT p.product_id, p.product_name, p.category,
                       p.stock_kg, p.reorder_point, p.supplier
                FROM products p
                WHERE p.source_type = 'butcher' AND p.stock_kg <= p.reorder_point
                ORDER BY
                    CASE
                        WHEN p.stock_kg = 0 THEN 1
                        ELSE 2
                    END,
                    p.stock_kg ASC
            ''')

            alerts = cursor.fetchall()

            if not alerts:
                print("\n✅ No low stock alerts")
            else:
                print(f"\n⚠️  LOW STOCK ALERTS ({len(alerts)} products):")
                print("=" * 80)

                for alert in alerts:
                    prod_id, name, category, stock, reorder_point, supplier = alert

                    stock_val = float(stock)
                    reorder_val = float(reorder_point)

                    if stock_val == 0:
                        icon = "🔴"
                        urgency = "OUT OF STOCK"
                    elif stock_val <= reorder_val / 2:
                        icon = "🟠"
                        urgency = "CRITICAL"
                    else:
                        icon = "🟡"
                        urgency = "LOW"

                    print(f"\n{icon} [{urgency}] ID {prod_id}: {name}")
                    print(f"   Category: {category}")
                    print(f"   Current Stock: {stock_val:.2f}kg")
                    print(f"   Reorder Point: {reorder_val:.2f}kg")
                    print(f"   Need to order: ~{(reorder_val * 2 - stock_val):.2f}kg")
                    if supplier:
                        print(f"   Supplier: {supplier}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing low stock alerts: {e}")
        print(f"❌ Error viewing alerts: {e}")

    input("\nPress Enter to continue...")
