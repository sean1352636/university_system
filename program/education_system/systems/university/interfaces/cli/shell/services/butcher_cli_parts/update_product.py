"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def update_product():
    """Update an existing product (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to update products")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Update Product")

        product_id = input("\nEnter Product ID to update: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        # Get current product details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_name, category, price_per_kg, description,
                       supplier, reorder_point, status
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
                input("\nPress Enter to continue...")
                return

            name, category, price, desc, supplier, reorder_point, status = product

            print("\nCurrent Product Details:")
            print(f"Name: {name}")
            print(f"Category: {category}")
            print(f"Price: {format_currency(float(price))}/kg")
            print(f"Status: {status}")
            if desc:
                print(f"Description: {desc}")
            if supplier:
                print(f"Supplier: {supplier}")
            print(f"Reorder Point: {float(reorder_point):.2f}kg")

            print("\n(Press Enter to keep current value)")

            # Update fields
            new_name = input(f"\nNew name [{name}]: ").strip() or name

            # Category
            print("\nSelect new category:")
            for idx, cat in enumerate(PRODUCT_CATEGORIES, 1):
                mark = "✓" if cat == category else " "
                print(f"{idx}. [{mark}] {cat}")

            cat_choice = input(f"Enter category number [current: {category}]: ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(PRODUCT_CATEGORIES):
                new_category = PRODUCT_CATEGORIES[int(cat_choice) - 1]
            else:
                new_category = category

            # Price
            price_str = input(f"New price per kg [{format_currency(float(price))}]: ").strip()
            new_price = validate_positive_number(price_str, "Price") if price_str else float(price)
            if new_price is None:
                new_price = float(price)

            # Description
            new_desc = input(f"New description [{desc or 'None'}]: ").strip()
            if not new_desc:
                new_desc = desc

            # Supplier
            new_supplier = input(f"New supplier [{supplier or 'None'}]: ").strip()
            if not new_supplier:
                new_supplier = supplier

            # Reorder point
            reorder_str = input(f"New reorder point [{float(reorder_point):.2f}kg]: ").strip()
            new_reorder = validate_positive_number(reorder_str, "Reorder point") if reorder_str else float(reorder_point)
            if new_reorder is None:
                new_reorder = float(reorder_point)

            # Status
            print(f"\nStatus: 1) Available 2) Unavailable [current: {status}]")
            status_choice = input("Select status (1/2): ").strip()
            if status_choice == '1':
                new_status = 'available'
            elif status_choice == '2':
                new_status = 'unavailable'
            else:
                new_status = status

            # Confirm
            print("\n📋 UPDATED PRODUCT SUMMARY:")
            print("-" * 80)
            print(f"Name: {new_name}")
            print(f"Category: {new_category}")
            print(f"Price: {format_currency(new_price)}/kg")
            print(f"Status: {new_status}")
            print(f"Reorder Point: {new_reorder:.2f}kg")
            if new_desc:
                print(f"Description: {new_desc}")
            if new_supplier:
                print(f"Supplier: {new_supplier}")

            confirm = input("\nUpdate this product? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Product update cancelled")
                input("\nPress Enter to continue...")
                return

            # Update product
            with transaction() as conn:
                conn.execute('''
                    UPDATE products
                    SET product_name = ?, category = ?, price_per_kg = ?,
                        description = ?, supplier = ?, reorder_point = ?,
                        status = ?, updated_at = ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (new_name, new_category, new_price, new_desc, new_supplier,
                      new_reorder, new_status, datetime.now().isoformat(), product_id))

            print("\n✅ Product updated successfully!")
            logger.info(f"Admin updated butcher product ID {product_id}")

    except Exception as e:
        logger.error(f"Error updating product: {e}")
        print(f"❌ Error updating product: {e}")

    input("\nPress Enter to continue...")
