from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_update, log_read
from education_system.university_system.modules.domain.commerce.services.shop_management import config


@log_update(module="shop", description="Updating stock levels")
def update_stock_levels():
    """Update stock levels for products"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to update stock levels.")
        return

    if not config.auth.check_permission('manage_inventory'):
        print("You don't have permission to update stock levels.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get product list
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1
            ORDER BY p.category, p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No active products found in the database.")
            conn.close()
            return

        # Display product list
        print("\nCurrent Stock Levels:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock'}")
        print("-" * 70)

        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']}")

        # Get product to update
        product_id = input("\nEnter product ID to update stock (or 'back' to return): ").strip().upper()

        if product_id.lower() == 'back':
            conn.close()
            return

        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.source_product_id = ?
            ''',
            [product_id]
        )

        product = cursor.fetchone()

        if not product:
            print(f"Product {product_id} not found.")
            conn.close()
            return

        # Display current stock
        print(f"\nUpdating stock for: {product['name']}")
        print(f"Current stock: {product['quantity']}")

        # Get new stock level
        while True:
            try:
                print("\nOptions:")
                print("1. Set exact stock level")
                print("2. Add to current stock")
                print("3. Remove from current stock")

                update_type = input("Choose option (1-3): ").strip()

                if update_type == '1':
                    # Set exact amount
                    new_quantity = int(input("Enter new stock level: ").strip())
                    if new_quantity < 0:
                        print("Stock cannot be negative.")
                        continue

                    change = new_quantity - product['quantity']
                    action = "Set"

                elif update_type == '2':
                    # Add to stock
                    add_quantity = int(input("Enter amount to add: ").strip())
                    if add_quantity < 0:
                        print("Amount to add cannot be negative.")
                        continue

                    new_quantity = product['quantity'] + add_quantity
                    change = add_quantity
                    action = "Added"

                elif update_type == '3':
                    # Remove from stock
                    remove_quantity = int(input("Enter amount to remove: ").strip())
                    if remove_quantity < 0:
                        print("Amount to remove cannot be negative.")
                        continue

                    if remove_quantity > product['quantity']:
                        print(f"Cannot remove more than current stock ({product['quantity']}).")
                        continue

                    new_quantity = product['quantity'] - remove_quantity
                    change = -remove_quantity
                    action = "Removed"

                else:
                    print("Invalid choice. Please select 1, 2, or 3.")
                    continue

                # Confirm update
                sign = "+" if change >= 0 else ""
                print(f"\nUpdate Summary:")
                print(f"Product: {product['name']} ({product_id})")
                print(f"Current Stock: {product['quantity']}")
                print(f"New Stock: {new_quantity} ({sign}{change})")

                confirm = input("Confirm update? (y/n): ").strip().lower()

                if confirm == 'y':
                    # Update stock
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        '''
                        UPDATE shop_inventory
                        SET quantity = ?, last_restock_date = ?
                        WHERE product_id = ?
                        ''',
                        [new_quantity, now, product_id]
                    )

                    conn.commit()
                    print(f"\n{action} stock successfully! New level: {new_quantity}")
                    break
                else:
                    print("Update cancelled.")
                    break

            except ValueError:
                print("Invalid input. Please enter a whole number.")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error updating stock: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error updating stock: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_update(module="shop", description="Restocking products")
def restock_products():
    """Restock products that are below threshold"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to restock products.")
        return

    if not config.auth.check_permission('manage_inventory'):
        print("You don't have permission to restock products.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get products below restock threshold
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY (i.quantity * 1.0 / i.restock_threshold), p.category, p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No products need restocking at this time.")
            conn.close()
            return

        # Display products needing restock
        print("\nProducts Needing Restock:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock':<15} {'Threshold'}")
        print("-" * 80)

        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<15} {product['restock_threshold']}")

        print("\nRestock Options:")
        print("1. Restock all products to threshold + 50%")
        print("2. Restock specific product")
        print("3. Cancel")

        choice = input("Choose option (1-3): ").strip()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if choice == '1':
            # Restock all products
            confirm = input("Are you sure you want to restock all listed products? (y/n): ").strip().lower()

            if confirm != 'y':
                print("Restock cancelled.")
                conn.close()
                return

            # Restock each product to threshold + 50% (batch update to avoid N+1)
            restock_data = []
            for product in products:
                new_quantity = int(product['restock_threshold'] * 1.5)
                if new_quantity <= product['quantity']:
                    new_quantity = product['restock_threshold'] * 2
                restock_data.append((new_quantity, now, product['product_id']))

            cursor.executemany(
                '''
                UPDATE shop_inventory
                SET quantity = ?, last_restock_date = ?
                WHERE product_id = ?
                ''',
                restock_data
            )

            conn.commit()
            print(f"\nRestocked {len(products)} products successfully!")

        elif choice == '2':
            # Restock specific product
            product_id = input("Enter product ID to restock: ").strip().upper()

            # Check if product is in the list
            product_to_restock = None
            for product in products:
                if product['product_id'] == product_id:
                    product_to_restock = product
                    break

            if not product_to_restock:
                print(f"Product {product_id} is not in the restock list.")
                conn.close()
                return

            # Get restock amount
            try:
                current = product_to_restock['quantity']
                threshold = product_to_restock['restock_threshold']
                suggested = threshold * 2 - current

                print(f"\nProduct: {product_to_restock['name']}")
                print(f"Current Stock: {current}")
                print(f"Threshold: {threshold}")
                print(f"Suggested Restock Amount: {suggested}")

                amount_input = input(f"Enter amount to add [default: {suggested}]: ").strip()

                if amount_input:
                    amount = int(amount_input)
                    if amount < 0:
                        print("Amount cannot be negative.")
                        conn.close()
                        return
                else:
                    amount = suggested

                new_quantity = current + amount

                # Update inventory
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET quantity = ?, last_restock_date = ?
                    WHERE product_id = ?
                    ''',
                    [new_quantity, now, product_id]
                )

                conn.commit()
                print(f"\nRestocked {product_id} successfully!")
                print(f"Previous stock: {current}")
                print(f"Added: {amount}")
                print(f"New stock: {new_quantity}")

            except ValueError:
                print("Invalid input. Please enter a whole number.")
                conn.close()
                return

        elif choice == '3':
            print("Restock cancelled.")
            conn.close()
            return

        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error restocking products: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error restocking products: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_read(module="shop", description="Viewing low stock")
def view_low_stock_products():
    """View products with low stock levels"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view low stock products.")
        return

    if not config.auth.check_permission('manage_inventory'):
        print("You don't have permission to view inventory details.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get products below threshold
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, p.price, i.quantity, i.restock_threshold,
                   i.last_restock_date, (i.quantity * 100.0 / i.restock_threshold) as stock_percent
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY stock_percent, p.category, p.name
            '''
        )

        low_stock = cursor.fetchall()

        if not low_stock:
            print("No products are below their restock threshold.")

            # Check for products getting close (within 20% above threshold)
            cursor.execute(
                '''
                SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold,
                       (i.quantity * 100.0 / i.restock_threshold) as stock_percent
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.is_active = 1
                  AND i.quantity > i.restock_threshold
                  AND i.quantity <= (i.restock_threshold * 1.2)
                ORDER BY stock_percent, p.category, p.name
                '''
            )

            warning_stock = cursor.fetchall()

            if warning_stock:
                print("\nProducts approaching restock threshold:")
                print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Stock':<8} {'Threshold':<10} {'Percent'}")
                print("-" * 85)

                for product in warning_stock:
                    percent = int(product['stock_percent'])
                    print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<8} {product['restock_threshold']:<10} {percent}%")

            conn.close()
            input("\nPress Enter to continue...")
            return

        # Display low stock products
        print("\nLow Stock Products:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Price':<10} {'Stock':<8} {'Threshold':<10} {'Percent':<8} {'Last Restock'}")
        print("-" * 110)

        for product in low_stock:
            price_formatted = f"\u00a3{product['price']:.2f}"
            percent = int(product['stock_percent'])
            last_restock = product['last_restock_date']

            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} "
                  f"{price_formatted:<10} {product['quantity']:<8} {product['restock_threshold']:<10} "
                  f"{percent}%{'':<8} {last_restock}")

        # Print summary
        total_value = sum(p['price'] * p['quantity'] for p in low_stock)
        print(f"\nTotal Low Stock Products: {len(low_stock)}")
        print(f"Total Value of Low Stock: \u00a3{total_value:.2f}")

        # Option to restock
        restock_option = input("\nWould you like to restock these products now? (y/n): ").strip().lower()

        if restock_option == 'y':
            conn.close()
            restock_products()
        else:
            conn.close()
            input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error viewing low stock: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing low stock: {e}")
        if 'conn' in locals():
            conn.close()


@log_update(module="shop", description="Adjusting restock thresholds")
def adjust_restock_thresholds():
    """Adjust restock thresholds for products"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to adjust restock thresholds.")
        return

    if not config.auth.check_permission('manage_inventory'):
        print("You don't have permission to adjust inventory settings.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get product list with inventory details
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1
            ORDER BY p.category, p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No active products found.")
            conn.close()
            return

        # Display products with thresholds
        print("\nCurrent Restock Thresholds:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock':<15} {'Threshold'}")
        print("-" * 80)

        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<15} {product['restock_threshold']}")

        print("\nAdjustment Options:")
        print("1. Adjust threshold for specific product")
        print("2. Adjust thresholds by category")
        print("3. Adjust all thresholds")
        print("4. Return to Inventory Menu")

        choice = input("Choose option (1-4): ").strip()

        if choice == '1':
            # Adjust specific product
            product_id = input("Enter product ID: ").strip().upper()

            cursor.execute(
                '''
                SELECT p.source_product_id as product_id, p.name, i.quantity, i.restock_threshold
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_product_id = ?
                ''',
                [product_id]
            )

            product = cursor.fetchone()

            if not product:
                print(f"Product {product_id} not found.")
                conn.close()
                return

            print(f"\nProduct: {product['name']} ({product_id})")
            print(f"Current Stock: {product['quantity']}")
            print(f"Current Threshold: {product['restock_threshold']}")

            try:
                new_threshold = int(input("Enter new threshold: ").strip())

                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return

                # Update threshold
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id = ?
                    ''',
                    [new_threshold, product_id]
                )

                conn.commit()
                print(f"Threshold updated successfully for {product_id}!")

            except ValueError:
                print("Invalid input. Please enter a whole number.")
                conn.close()
                return

        elif choice == '2':
            # Adjust by category
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY category")
            categories = cursor.fetchall()

            print("\nAvailable Categories:")
            for i, category in enumerate(categories):
                print(f"{i+1}. {category['category']}")

            try:
                cat_choice = int(input("Select category number: ").strip())

                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return

                selected_category = categories[cat_choice-1]['category']

                # Get current thresholds for this category
                cursor.execute(
                    '''
                    SELECT AVG(i.restock_threshold) as avg_threshold
                    FROM products p
                    JOIN shop_inventory i ON p.source_product_id = i.product_id
                    WHERE p.category = ? AND p.is_active = 1
                    ''',
                    [selected_category]
                )

                avg_threshold = cursor.fetchone()['avg_threshold']

                print(f"\nCategory: {selected_category}")
                print(f"Average Current Threshold: {avg_threshold:.1f}")

                new_threshold = int(input("Enter new threshold for all products in this category: ").strip())

                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return

                # Update thresholds for this category
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id IN (
                        SELECT p.source_product_id FROM products p
                        WHERE p.source_type = 'shop' AND p.category = ? AND p.is_active = 1
                    )
                    ''',
                    [new_threshold, selected_category]
                )

                affected = cursor.rowcount
                conn.commit()
                print(f"Updated thresholds for {affected} products in {selected_category} category!")

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif choice == '3':
            # Adjust all thresholds
            try:
                # Get current average
                cursor.execute(
                    '''
                    SELECT AVG(i.restock_threshold) as avg_threshold
                    FROM shop_inventory i
                    JOIN products p ON i.product_id = p.source_product_id AND p.source_type = 'shop'
                    WHERE p.is_active = 1
                    '''
                )

                avg_threshold = cursor.fetchone()['avg_threshold']
                print(f"\nCurrent Average Threshold: {avg_threshold:.1f}")

                new_threshold = int(input("Enter new threshold for all active products: ").strip())

                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return

                # Update all thresholds
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id IN (
                        SELECT p.source_product_id FROM products p
                        WHERE p.source_type = 'shop' AND p.is_active = 1
                    )
                    ''',
                    [new_threshold]
                )

                affected = cursor.rowcount
                conn.commit()
                print(f"Updated thresholds for {affected} products to {new_threshold}!")

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif choice == '4':
            print("Returning to Inventory Menu...")
            conn.close()
            return

        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error adjusting thresholds: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error adjusting thresholds: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


def get_low_stock_alert():
    """Get alert message for low stock products"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*) as low_stock_count
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold
            '''
        )

        result = cursor.fetchone()
        low_stock_count = result[0] if result else 0

        conn.close()

        if low_stock_count > 0:
            return f"\u26a0\ufe0f  Warning: {low_stock_count} product(s) are low on stock!"

        return None

    except Exception:
        return None


def send_low_stock_notification():
    """Send notification for low stock items (placeholder for email/SMS)"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get low stock items
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY (i.quantity * 1.0 / i.restock_threshold)
            '''
        )

        low_stock_items = cursor.fetchall()
        conn.close()

        if not low_stock_items:
            return

        # In a real system, this would send email/SMS notifications
        print(f"\n\U0001f4e7 Low Stock Notification would be sent for {len(low_stock_items)} items:")
        for item in low_stock_items:
            print(f"  - {item['name']} ({item['product_id']}): {item['quantity']} remaining")

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error sending low stock notification: {e}")


def get_inventory_valuation():
    """Calculate total inventory value"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT SUM(p.price * i.quantity) as total_value,
                   COUNT(p.source_product_id) as product_count,
                   SUM(i.quantity) as total_quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1
            '''
        )

        result = cursor.fetchone()
        conn.close()

        return {
            'total_value': result[0] or 0,
            'product_count': result[1] or 0,
            'total_quantity': result[2] or 0
        }

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}
