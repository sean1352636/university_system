"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def browse_products_by_category():
    """Browse products filtered by category"""
    try:
        print_subheader("Browse Products by Category")

        # Display categories
        print("\n📦 Product Categories:")
        for idx, category in enumerate(PRODUCT_CATEGORIES, 1):
            print(f"{idx}. {category}")
        print("0. View All Categories")

        choice = input("\nSelect category (0 for all): ").strip()

        category_filter = None
        if choice.isdigit() and 1 <= int(choice) <= len(PRODUCT_CATEGORIES):
            category_filter = PRODUCT_CATEGORIES[int(choice) - 1]

        with get_connection() as conn:
            if category_filter:
                cursor = conn.execute('''
                    SELECT product_id, product_name, category, price_per_kg,
                           stock_kg, description, status
                    FROM products
                    WHERE source_type = 'butcher' AND category = ? AND status = 'available'
                    ORDER BY product_name
                ''', (category_filter,))
            else:
                cursor = conn.execute('''
                    SELECT product_id, product_name, category, price_per_kg,
                           stock_kg, description, status
                    FROM products
                    WHERE source_type = 'butcher' AND status = 'available'
                    ORDER BY category, product_name
                ''')

            products = cursor.fetchall()

            if not products:
                print("\n❌ No products found in this category")
            else:
                print(f"\n🥩 PRODUCTS{f' - {category_filter}' if category_filter else ''}:")
                print("-" * 80)

                current_category = None
                for product in products:
                    try:
                        prod_id, name, category, price, stock, desc, status = product

                        if not category_filter and category != current_category:
                            print(f"\n📦 {category}:")
                            current_category = category

                        stock_icon = get_stock_status_icon(float(stock))
                        print(f"  {stock_icon} ID {prod_id}: {name}")
                        print(f"      Price: {format_currency(float(price))}/kg | Stock: {float(stock):.2f}kg")
                        if desc:
                            print(f"      {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying product: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error browsing products: {e}")
        print(f"❌ Error browsing products: {e}")

    input("\nPress Enter to continue...")
