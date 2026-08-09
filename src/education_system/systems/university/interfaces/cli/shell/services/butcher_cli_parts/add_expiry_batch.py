"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def add_expiry_batch():
    """Add a new batch with expiry date"""
    try:
        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_name FROM products WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()
            if not product:
                print("❌ Product not found")
                return

            name = product[0]

            print(f"\n📦 Product: {name}")

            batch_number = input("Batch number: ").strip()
            if not batch_number:
                batch_number = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            quantity_str = input("Quantity (kg): ").strip()
            quantity = validate_positive_number(quantity_str, "Quantity")
            if quantity is None:
                return

            expiry_str = input("Expiry date (YYYY-MM-DD): ").strip()
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date().isoformat()
            except ValueError:
                print("❌ Invalid date format")
                return

            with transaction() as trans_conn:
                trans_conn.execute('''
                    INSERT INTO butcher_product_expiry
                    (product_id, batch_number, quantity_kg, expiry_date)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, batch_number, quantity, expiry_date))

            print(f"\n✅ Expiry batch added: {batch_number}")
            logger.info(f"Added expiry batch {batch_number} for product {product_id}")

    except Exception as e:
        logger.error(f"Error adding expiry batch: {e}")
        print(f"❌ Error: {e}")
