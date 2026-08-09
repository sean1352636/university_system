"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def add_product():
    """Add a new product (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to add products")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Add New Product")

        # Get product details
        name = input("\nProduct Name: ").strip()
        if not name:
            print("❌ Product name cannot be empty")
            input("\nPress Enter to continue...")
            return

        # Category selection
        print("\nSelect Category:")
        for idx, category in enumerate(PRODUCT_CATEGORIES, 1):
            print(f"{idx}. {category}")

        cat_choice = input("Enter category number: ").strip()
        if not cat_choice.isdigit() or not (1 <= int(cat_choice) <= len(PRODUCT_CATEGORIES)):
            print("❌ Invalid category selection")
            input("\nPress Enter to continue...")
            return

        category = PRODUCT_CATEGORIES[int(cat_choice) - 1]

        # Price
        price_str = input("Price per kg (GBP): ").strip()
        price = validate_positive_number(price_str, "Price")
        if price is None:
            input("\nPress Enter to continue...")
            return

        # Initial stock
        stock_str = input("Initial stock (kg): ").strip()
        stock = validate_positive_number(stock_str, "Stock")
        if stock is None:
            input("\nPress Enter to continue...")
            return

        # Optional fields
        description = input("Description (optional): ").strip()
        supplier = input("Supplier (optional): ").strip()

        reorder_str = input("Reorder point in kg (default 5.0): ").strip()
        reorder_point = 5.0
        if reorder_str:
            reorder_point = validate_positive_number(reorder_str, "Reorder point")
            if reorder_point is None:
                reorder_point = 5.0

        # Confirm
        print("\n📋 PRODUCT SUMMARY:")
        print("-" * 80)
        print(f"Name: {name}")
        print(f"Category: {category}")
        print(f"Price: {format_currency(price)}/kg")
        print(f"Initial Stock: {stock:.2f}kg")
        print(f"Reorder Point: {reorder_point:.2f}kg")
        if description:
            print(f"Description: {description}")
        if supplier:
            print(f"Supplier: {supplier}")

        confirm = input("\nAdd this product? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Product addition cancelled")
            input("\nPress Enter to continue...")
            return

        # Add product
        with transaction() as conn:
            conn.execute('''
                INSERT INTO products
                (source_type, product_name, category, price_per_kg, stock_kg, description,
                 supplier, reorder_point, status, created_at, updated_at)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)
            ''', (name, category, price, stock, description, supplier,
                  reorder_point, datetime.now().isoformat(), datetime.now().isoformat()))

            product_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        print(f"\n✅ Product added successfully! (ID: {product_id})")
        logger.info(f"Admin added new butcher product: {name} (ID: {product_id})")

    except Exception as e:
        logger.error(f"Error adding product: {e}")
        print(f"❌ Error adding product: {e}")

    input("\nPress Enter to continue...")
