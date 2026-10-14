"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def inventory_valuation_report():
    """Generate inventory valuation report (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view reports")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Inventory Valuation Report")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT category,
                       COUNT(*) as product_count,
                       SUM(stock_kg) as total_stock,
                       SUM(stock_kg * price_per_kg) as total_value
                FROM products
                WHERE source_type = 'butcher'
                GROUP BY category
                ORDER BY total_value DESC
            ''')

            categories = cursor.fetchall()

            # Overall totals
            total_cursor = conn.execute('''
                SELECT COUNT(*), SUM(stock_kg), SUM(stock_kg * price_per_kg)
                FROM products
                WHERE source_type = 'butcher'
            ''')

            total_products, total_stock, total_value = total_cursor.fetchone()

            print("\n" + "=" * 80)
            print("              INVENTORY VALUATION REPORT")
            print("=" * 80)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n📦 BY CATEGORY:")
            print("-" * 80)
            print(f"{'Category':<20} {'Products':<12} {'Stock (kg)':<15} {'Value':>15}")
            print("-" * 80)

            for category, count, stock, value in categories:
                print(f"{category:<20} {count:<12} {float(stock):<15.2f} {format_currency(float(value)):>15}")

            print("-" * 80)
            print(f"{'TOTAL':<20} {total_products:<12} {float(total_stock):<15.2f} {format_currency(float(total_value)):>15}")
            print("=" * 80)

            # Low stock warning
            low_stock_cursor = conn.execute('''
                SELECT COUNT(*) FROM products
                WHERE source_type = 'butcher' AND stock_kg <= reorder_point
            ''')
            low_stock_count = low_stock_cursor.fetchone()[0]

            if low_stock_count > 0:
                print(f"\n⚠️  {low_stock_count} product(s) at or below reorder point")

    except Exception as e:
        logger.error(f"Error generating valuation report: {e}")
        print(f"❌ Error generating report: {e}")

    input("\nPress Enter to continue...")
