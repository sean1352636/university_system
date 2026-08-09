"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def search_products():
    """Search products by name"""
    try:
        print_subheader("Search Products")

        search_term = input("\nEnter product name to search: ").strip()

        if not search_term:
            print("❌ Search term cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_id, product_name, category, price_per_kg,
                       stock_kg, description, status
                FROM products
                WHERE source_type = 'butcher' AND (product_name LIKE ? OR description LIKE ?)
                ORDER BY
                    CASE WHEN product_name LIKE ? THEN 1 ELSE 2 END,
                    product_name
            ''', (f'%{search_term}%', f'%{search_term}%', f'{search_term}%'))

            products = cursor.fetchall()

            if not products:
                print(f"\n❌ No products found matching '{search_term}'")
            else:
                print(f"\n🔍 SEARCH RESULTS ({len(products)} found):")
                print("-" * 80)

                for product in products:
                    try:
                        prod_id, name, category, price, stock, desc, status = product

                        stock_icon = get_stock_status_icon(float(stock))
                        status_text = "✅ Available" if status == 'available' else "❌ Unavailable"

                        print(f"\n  {stock_icon} ID {prod_id}: {name} ({category})")
                        print(f"      Price: {format_currency(float(price))}/kg | Stock: {float(stock):.2f}kg")
                        print(f"      Status: {status_text}")
                        if desc:
                            print(f"      {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying search result: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error searching products: {e}")
        print(f"❌ Error searching products: {e}")

    input("\nPress Enter to continue...")
