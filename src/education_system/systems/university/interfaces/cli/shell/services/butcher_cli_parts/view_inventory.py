"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_inventory():
    """View inventory status (staff only)"""
    if not is_admin():
        print("❌ You don't have permission to view inventory")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Inventory Status")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, product_name, category, stock_kg,
                       price_per_kg, reorder_point, status
                FROM products
                WHERE source_type = 'butcher'
                ORDER BY
                    CASE
                        WHEN stock_kg <= reorder_point THEN 1
                        ELSE 2
                    END,
                    category, product_name
            ''')
            products = cursor.fetchall()

            if not products:
                print("\n❌ No products in inventory")
            else:
                # Calculate totals
                total_value = 0.0
                low_stock_count = 0
                out_of_stock_count = 0

                print(f"\n📦 INVENTORY STATUS ({len(products)} products):")
                print("=" * 80)

                current_category = None
                for product in products:
                    try:
                        (prod_id, name, category, stock, price,
                         reorder_point, status) = product

                        stock_val = float(stock)
                        price_val = float(price)
                        reorder_val = float(reorder_point)
                        item_value = stock_val * price_val
                        total_value += item_value

                        if category != current_category:
                            if current_category is not None:
                                print()
                            print(f"\n📦 {category}:")
                            print("-" * 80)
                            current_category = category

                        stock_icon = get_stock_status_icon(stock_val)

                        alert = ""
                        if stock_val == 0:
                            alert = " ⚠️  OUT OF STOCK"
                            out_of_stock_count += 1
                        elif stock_val <= reorder_val:
                            alert = f" ⚠️  LOW STOCK (reorder at {reorder_val:.2f}kg)"
                            low_stock_count += 1

                        status_mark = "✓" if status == 'available' else "✗"

                        print(f"  {stock_icon} [{status_mark}] ID {prod_id}: {name}")
                        print(f"      Stock: {stock_val:.2f}kg | Value: {format_currency(item_value)} | {format_currency(price_val)}/kg{alert}")

                    except Exception as e:
                        logger.error(f"Error displaying inventory item: {e}")
                        continue

                # Summary
                print("\n" + "=" * 80)
                print("📊 INVENTORY SUMMARY:")
                print(f"   Total Products: {len(products)}")
                print(f"   Total Value: {format_currency(total_value)}")
                print(f"   Low Stock Alerts: {low_stock_count}")
                print(f"   Out of Stock: {out_of_stock_count}")
                print("=" * 80)

    except Exception as e:
        logger.error(f"Error viewing inventory: {e}")
        print(f"❌ Error viewing inventory: {e}")

    input("\nPress Enter to continue...")
