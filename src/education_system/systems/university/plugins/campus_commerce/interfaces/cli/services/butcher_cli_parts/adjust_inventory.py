"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def adjust_inventory():
    """Adjust inventory levels (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to adjust inventory")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Adjust Inventory")

        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT name, stock_quantity
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
                input("\nPress Enter to continue...")
                return

            name, current_stock = product

            print(f"\n📦 Product: {name}")
            print(f"   Current Stock: {float(current_stock):.2f}kg")

            # Adjustment type
            print("\n🔧 Adjustment Type:")
            print("1. Add stock (restocking)")
            print("2. Remove stock (wastage/damage)")
            print("3. Set exact stock level")

            adj_type = input("\nSelect type (1-3): ").strip()

            if adj_type not in ['1', '2', '3']:
                print("❌ Invalid adjustment type")
                input("\nPress Enter to continue...")
                return

            if adj_type in ['1', '2']:
                quantity_str = input("Enter quantity (kg): ").strip()
                quantity = validate_positive_number(quantity_str, "Quantity")

                if quantity is None:
                    input("\nPress Enter to continue...")
                    return

                if adj_type == '2':
                    if quantity > float(current_stock):
                        print(f"❌ Cannot remove {quantity:.2f}kg - only {float(current_stock):.2f}kg in stock")
                        input("\nPress Enter to continue...")
                        return
                    quantity = -quantity  # Make negative for removal
                    new_stock = float(current_stock) + quantity
                else:
                    new_stock = float(current_stock) + quantity

            else:  # Set exact level
                new_stock_str = input("Enter new stock level (kg): ").strip()
                new_stock = validate_positive_number(new_stock_str, "Stock level")

                if new_stock is None:
                    new_stock = 0.0

                quantity = new_stock - float(current_stock)

            # Reason
            print("\n📝 Reason for adjustment:")
            print("1. Restocking")
            print("2. Wastage")
            print("3. Damage")
            print("4. Correction")
            print("5. Other")

            reason_choice = input("Select reason (1-5): ").strip()
            reasons = {
                '1': 'Restocking',
                '2': 'Wastage',
                '3': 'Damage',
                '4': 'Stock correction',
                '5': 'Other'
            }
            reason = reasons.get(reason_choice, 'Other')

            if reason == 'Other':
                custom_reason = input("Enter reason: ").strip()
                if custom_reason:
                    reason = custom_reason

            notes = input("Additional notes (optional): ").strip()

            # Confirm
            print("\n📋 ADJUSTMENT SUMMARY:")
            print("-" * 80)
            print(f"Product: {name}")
            print(f"Current Stock: {float(current_stock):.2f}kg")
            print(f"Adjustment: {quantity:+.2f}kg")
            print(f"New Stock: {new_stock:.2f}kg")
            print(f"Reason: {reason}")
            if notes:
                print(f"Notes: {notes}")

            confirm = input("\nApply adjustment? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Adjustment cancelled")
                input("\nPress Enter to continue...")
                return

            # Apply adjustment
            user = get_current_user()

            with transaction() as trans_conn:
                # Update stock
                trans_conn.execute('''
                    UPDATE products
                    SET stock_quantity = ?, updated_at = ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (new_stock, datetime.now().isoformat(), product_id))

                # Log adjustment
                trans_conn.execute('''
                    INSERT INTO butcher_inventory_adjustments
                    (product_id, quantity_change, reason, adjusted_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (product_id, quantity, reason, user.get('username', 'admin'), notes))

                # Check for low stock alert
                cursor = trans_conn.execute('''
                    SELECT min_stock_level FROM products WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (product_id,))
                reorder_point = cursor.fetchone()[0]

                if new_stock <= float(reorder_point):
                    trans_conn.execute('''
                        INSERT INTO butcher_stock_alerts
                        (product_id, alert_type, alert_date)
                        VALUES (?, 'low_stock', ?)
                    ''', (product_id, datetime.now().isoformat()))

            print("\n✅ Inventory adjusted successfully!")
            print(f"   New stock level: {new_stock:.2f}kg")

            logger.info(f"Admin {user.get('username')} adjusted inventory for product {product_id}: {quantity:+.2f}kg")

    except Exception as e:
        logger.error(f"Error adjusting inventory: {e}")
        print(f"❌ Error adjusting inventory: {e}")

    input("\nPress Enter to continue...")
