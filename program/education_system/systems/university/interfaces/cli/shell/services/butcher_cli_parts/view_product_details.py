"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_product_details():
    """View detailed information about a specific product"""
    try:
        print_subheader("Product Details")

        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, product_name, category, price_per_kg,
                       stock_kg, description, status, reorder_point, supplier,
                       created_at, updated_at
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
            else:
                (prod_id, name, category, price, stock, desc, status,
                 reorder_point, supplier, created, updated) = product

                stock_icon = get_stock_status_icon(float(stock))

                print(f"\n{stock_icon} PRODUCT DETAILS:")
                print("-" * 80)
                print(f"ID: {prod_id}")
                print(f"Name: {name}")
                print(f"Category: {category}")
                print(f"Price: {format_currency(float(price))}/kg")
                print(f"Stock: {float(stock):.2f}kg")
                print(f"Status: {status.upper()}")
                print(f"Reorder Point: {float(reorder_point):.2f}kg")
                if supplier:
                    print(f"Supplier: {supplier}")
                if desc:
                    print(f"Description: {desc}")
                print(f"Created: {format_date(created)}")
                print(f"Updated: {format_date(updated)}")

                # Check for expiry information
                expiry_cursor = conn.execute('''
                    SELECT batch_number, quantity_kg, expiry_date, received_date
                    FROM butcher_product_expiry
                    WHERE product_id = ? AND status = 'active'
                    ORDER BY expiry_date
                ''', (product_id,))

                expiry_batches = expiry_cursor.fetchall()
                if expiry_batches:
                    print("\n📅 Expiry Information:")
                    for batch in expiry_batches:
                        batch_num, qty, exp_date, recv_date = batch
                        print(f"  Batch {batch_num}: {float(qty):.2f}kg - Expires: {exp_date}")

                # Stock alert check
                if float(stock) <= float(reorder_point):
                    print(f"\n⚠️  LOW STOCK ALERT: Current stock ({float(stock):.2f}kg) is at or below reorder point ({float(reorder_point):.2f}kg)")

    except Exception as e:
        logger.error(f"Error viewing product details: {e}")
        print(f"❌ Error viewing product details: {e}")

    input("\nPress Enter to continue...")
