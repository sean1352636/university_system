import time
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import log_create, log_update, log_read
from education_system.systems.university.domain.operations.commerce.services.shop_management import config


@log_create(module="shop", description="Adding new product")
def add_new_product():
    """Add a new product to the shop"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to add products.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to add products.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nAdd New Product:")

        # Generate product ID
        cursor.execute("SELECT MAX(SUBSTR(source_product_id, 2)) FROM products WHERE source_type = 'shop' AND source_product_id LIKE 'P%'")
        result = cursor.fetchone()

        try:
            if result[0]:
                next_id = int(result[0]) + 1
            else:
                next_id = 1
            product_id = f"P{next_id:03d}"
        except (ValueError, TypeError):
            product_id = f"P{int(time.time())}"

        print(f"Generated Product ID: {product_id}")

        # Get product details
        name = None
        while not name:
            name = input("Product Name: ").strip()
            if not name:
                print("Product name cannot be empty.")

        description = input("Description: ").strip()

        # Get price with validation
        price = None
        while price is None:
            try:
                price_input = input("Price (£): ").strip()
                price = float(price_input)
                if price < 0:
                    print("Price cannot be negative.")
                    price = None
            except ValueError:
                print("Invalid price. Please enter a valid number.")

        # Get category
        cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' ORDER BY category")
        categories = cursor.fetchall()

        print("\nExisting Categories:")
        if categories:
            for i, category in enumerate(categories):
                print(f"{i+1}. {category[0]}")
            print(f"{len(categories)+1}. Other (create new)")

            try:
                category_choice = int(input(f"Select category (1-{len(categories)+1}): "))

                if 1 <= category_choice <= len(categories):
                    category = categories[category_choice-1][0]
                else:
                    category = input("Enter new category name: ").strip()
            except ValueError:
                category = input("Enter category name: ").strip()
        else:
            category = input("Enter category name: ").strip()

        # Get tax rate (with default)
        tax_rate = 0.2  # Default 20%
        try:
            tax_input = input("Tax Rate (default 20%): ").strip()
            if tax_input:
                tax_rate = float(tax_input) / 100
        except ValueError:
            print("Invalid tax rate. Using default 20%.")

        # Get initial inventory
        initial_stock = None
        while initial_stock is None:
            try:
                stock_input = input("Initial Stock Quantity: ").strip()
                initial_stock = int(stock_input)
                if initial_stock < 0:
                    print("Stock cannot be negative.")
                    initial_stock = None
            except ValueError:
                print("Invalid quantity. Please enter a whole number.")

        # Get restock threshold
        restock_threshold = 5  # Default
        try:
            threshold_input = input("Restock Threshold (default 5): ").strip()
            if threshold_input:
                restock_threshold = int(threshold_input)
                if restock_threshold < 0:
                    print("Threshold cannot be negative. Using default 5.")
                    restock_threshold = 5
        except ValueError:
            print("Invalid threshold. Using default 5.")

        # Current datetime for timestamps
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert product
        cursor.execute(
            '''
            INSERT INTO products
            (source_product_id, source_type, name, description, price, category, created_at, updated_at, tax_rate, is_active)
            VALUES (?, 'shop', ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [product_id, name, description, price, category, now, now, tax_rate, 1]
        )

        # Insert inventory
        cursor.execute(
            '''
            INSERT INTO shop_inventory
            (product_id, quantity, last_restock_date, restock_threshold)
            VALUES (?, ?, ?, ?)
            ''',
            [product_id, initial_stock, now, restock_threshold]
        )

        conn.commit()

        print(f"\nProduct {product_id} added successfully!")
        print(f"Name: {name}")
        print(f"Price: £{price:.2f}")
        print(f"Category: {category}")
        print(f"Initial Stock: {initial_stock}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error adding product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error adding product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_update(module="shop", description="Editing product")
def edit_product():
    """Edit an existing product"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to edit products.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to edit products.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get product list
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
                   p.tax_rate, p.is_active, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop'
            ORDER BY p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No products found in the database.")
            conn.close()
            return

        # Display product list
        print("\nProduct List:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Active'}")
        print("-" * 70)

        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"
            print(f"{product['source_product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['quantity']:<8} {active_status}")

        # Get product to edit
        product_id = input("\nEnter product ID to edit: ").strip().upper()

        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
                   p.tax_rate, p.is_active, i.quantity, i.restock_threshold
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

        # Display current product details
        print(f"\nEditing Product: {product['product_id']} - {product['name']}")
        print("Current details:")
        print(f"Name: {product['name']}")
        print(f"Description: {product['description']}")
        print(f"Price: £{product['price']:.2f}")
        print(f"Category: {product['category']}")
        print(f"Tax Rate: {product['tax_rate']*100:.1f}%")
        print(f"Active: {'Yes' if product['is_active'] else 'No'}")
        print(f"Stock: {product['quantity']}")
        print(f"Restock Threshold: {product['restock_threshold']}")

        # Get updated details
        print("\nEnter new details (leave blank to keep current value):")

        name = input(f"Name [{product['name']}]: ").strip()
        if not name:
            name = product['name']

        description = input(f"Description [{product['description']}]: ").strip()
        if not description:
            description = product['description']

        price = None
        while price is None:
            try:
                price_input = input(f"Price (£) [{product['price']:.2f}]: ").strip()
                if not price_input:
                    price = product['price']
                else:
                    price = float(price_input)
                    if price < 0:
                        print("Price cannot be negative.")
                        price = None
            except ValueError:
                print("Invalid price. Please enter a valid number.")

        category = input(f"Category [{product['category']}]: ").strip()
        if not category:
            category = product['category']

        tax_rate = None
        while tax_rate is None:
            try:
                tax_input = input(f"Tax Rate % [{product['tax_rate']*100:.1f}]: ").strip()
                if not tax_input:
                    tax_rate = product['tax_rate']
                else:
                    tax_rate = float(tax_input) / 100
                    if tax_rate < 0:
                        print("Tax rate cannot be negative.")
                        tax_rate = None
            except ValueError:
                print("Invalid tax rate. Please enter a valid number.")

        # Update product
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            '''
            UPDATE products
            SET name = ?, description = ?, price = ?, category = ?,
                tax_rate = ?, updated_at = ?
            WHERE source_type = 'shop' AND source_product_id = ?
            ''',
            [name, description, price, category, tax_rate, now, product_id]
        )

        conn.commit()

        print(f"\nProduct {product_id} updated successfully!")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error editing product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error editing product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_update(module="shop", description="Toggling product status")
def toggle_product_status():
    """Activate or deactivate a product"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to change product status.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to change product status.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get product list
        cursor.execute(
            '''
            SELECT p.*, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop'
            ORDER BY p.is_active DESC, p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No products found in the database.")
            conn.close()
            return

        # Display product list
        print("\nProduct List:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Active'}")
        print("-" * 70)

        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"
            print(f"{product['source_product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['quantity']:<8} {active_status}")

        # Get product to toggle
        product_id = input("\nEnter product ID to toggle status: ").strip().upper()

        cursor.execute(
            '''
            SELECT source_product_id as product_id, name, description, price, category,
                   tax_rate, is_active
            FROM products
            WHERE source_type = 'shop' AND source_product_id = ?
            ''',
            [product_id]
        )

        product = cursor.fetchone()

        if not product:
            print(f"Product {product_id} not found.")
            conn.close()
            return

        # Toggle status
        new_status = 0 if product['is_active'] else 1
        status_text = "activated" if new_status else "deactivated"

        confirm = input(f"Are you sure you want to {status_text.lower()} {product['name']}? (y/n): ").strip().lower()

        if confirm != 'y':
            print("Operation cancelled.")
            conn.close()
            return

        cursor.execute(
            '''
            UPDATE products
            SET is_active = ?, updated_at = ?
            WHERE source_type = 'shop' AND source_product_id = ?
            ''',
            [new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id]
        )

        conn.commit()

        print(f"\nProduct {product_id} - {product['name']} has been {status_text}.")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error toggling product status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error toggling product status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_read(module="shop", description="Viewing all products")
def view_all_products():
    """View all products in the shop database"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view all products.")
        return

    if not config.auth.check_permission('manage_products') and not config.auth.check_permission('view_products'):
        print("You don't have permission to view products.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all products with inventory
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
                   p.created_at, p.updated_at, p.tax_rate, p.is_active,
                   i.quantity, i.restock_threshold, i.last_restock_date
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop'
            ORDER BY p.category, p.name
            '''
        )

        products = cursor.fetchall()

        if not products:
            print("No products found in the database.")
            conn.close()
            return

        # Display products by category
        current_category = None

        print("\nProduct Inventory:")
        for product in products:
            # Print category header if changed
            if product['category'] != current_category:
                current_category = product['category']
                print(f"\n--- {current_category} ---")
                print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Threshold':<10} {'Active'}")
                print("-" * 75)

            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"

            # Highlight low stock with asterisk
            stock_display = f"{product['quantity']}"
            if product['quantity'] <= product['restock_threshold']:
                stock_display += "*"

            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {stock_display:<8} {product['restock_threshold']:<10} {active_status}")

        # Show legend for low stock
        print("\n* indicates stock below or at restock threshold")

        # Count statistics
        total_products = len(products)
        active_products = sum(1 for p in products if p['is_active'])
        low_stock = sum(1 for p in products if p['quantity'] <= p['restock_threshold'])

        print(f"\nTotal Products: {total_products}")
        print(f"Active Products: {active_products}")
        print(f"Products with Low Stock: {low_stock}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error viewing products: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing products: {e}")
        if 'conn' in locals():
            conn.close()


def search_products(search_term, category=None, min_price=None, max_price=None):
    """Advanced product search function"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = '''
        SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
               p.tax_rate, p.is_active, i.quantity
        FROM products p
        JOIN shop_inventory i ON p.source_product_id = i.product_id
        WHERE p.source_type = 'shop' AND p.is_active = 1
        '''
        params = []

        if search_term:
            query += ' AND (p.name LIKE ? OR p.description LIKE ?)'
            params.extend([f'%{search_term}%', f'%{search_term}%'])

        if category:
            query += ' AND p.category = ?'
            params.append(category)

        if min_price is not None:
            query += ' AND p.price >= ?'
            params.append(min_price)

        if max_price is not None:
            query += ' AND p.price <= ?'
            params.append(max_price)

        query += ' ORDER BY p.name'

        cursor.execute(query, params)
        results = cursor.fetchall()

        conn.close()
        return results

    except Exception:
        if 'conn' in locals():
            conn.close()
        return []


def get_popular_products(limit=10, days=30):
    """Get most popular products based on recent sales"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.category, p.price,
                   SUM(ti.quantity) as total_sold,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at >= ? AND p.is_active = 1
            GROUP BY p.source_product_id
            ORDER BY total_sold DESC, transaction_count DESC
            LIMIT ?
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S'), limit]
        )

        popular_products = cursor.fetchall()
        conn.close()

        return popular_products

    except Exception:
        if 'conn' in locals():
            conn.close()
        return []


def validate_product_data(product_data):
    """Validate product data before insertion/update"""
    errors = []

    # Required fields
    if not product_data.get('name', '').strip():
        errors.append("Product name is required")

    if not product_data.get('price'):
        errors.append("Product price is required")
    else:
        try:
            price = float(product_data['price'])
            if price < 0:
                errors.append("Product price cannot be negative")
        except (ValueError, TypeError):
            errors.append("Product price must be a valid number")

    if not product_data.get('category', '').strip():
        errors.append("Product category is required")

    # Optional validations
    if 'tax_rate' in product_data:
        try:
            tax_rate = float(product_data['tax_rate'])
            if tax_rate < 0 or tax_rate > 1:
                errors.append("Tax rate must be between 0 and 1 (0-100%)")
        except (ValueError, TypeError):
            errors.append("Tax rate must be a valid number")

    return errors


def quick_add_product():
    """Quick product addition with minimal input"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to add products.")
        return False

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to add products.")
        return False

    try:
        print("\n🚀 Quick Add Product")
        print("-" * 20)

        # Get basic info
        name = input("Product name: ").strip()
        if not name:
            print("Product name is required.")
            return False

        try:
            price = float(input("Price (£): ").strip())
            if price < 0:
                print("Price cannot be negative.")
                return False
        except ValueError:
            print("Invalid price.")
            return False

        category = input("Category: ").strip() or "General"

        try:
            stock = int(input("Initial stock: ").strip() or "10")
            if stock < 0:
                print("Stock cannot be negative.")
                return False
        except ValueError:
            print("Invalid stock quantity.")
            return False

        # Generate product ID
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(SUBSTR(source_product_id, 2)) FROM products WHERE source_type = 'shop' AND source_product_id LIKE 'P%'")
        result = cursor.fetchone()

        try:
            if result[0]:
                next_id = int(result[0]) + 1
            else:
                next_id = 1
            product_id = f"P{next_id:03d}"
        except (ValueError, TypeError):
            product_id = f"P{int(time.time())}"

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert product
        cursor.execute(
            '''
            INSERT INTO products
            (source_product_id, source_type, name, description, price, category, created_at, updated_at, tax_rate, is_active)
            VALUES (?, 'shop', ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [product_id, name, f"Quick-added product: {name}", price, category, now, now, 0.2, 1]
        )

        # Insert inventory
        cursor.execute(
            '''
            INSERT INTO shop_inventory
            (product_id, quantity, last_restock_date, restock_threshold)
            VALUES (?, ?, ?, ?)
            ''',
            [product_id, stock, now, max(5, stock // 4)]
        )

        conn.commit()
        conn.close()

        print(f"✅ Product {product_id} '{name}' added successfully!")
        return True

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        print(f"❌ Error adding product: {e}")
        return False


def bulk_update_prices():
    """Bulk update prices by category or percentage"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to update prices.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to update prices.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\n💰 Bulk Price Update")
        print("-" * 20)

        print("Update options:")
        print("1. Update all prices by percentage")
        print("2. Update prices by category")
        print("3. Set fixed price for category")

        choice = input("Select option (1-3): ").strip()

        if choice == '1':
            # Update all prices by percentage
            try:
                percentage = float(input("Enter percentage change (+/-): ").strip())

                cursor.execute(
                    '''
                    UPDATE products
                    SET price = price * (1 + ? / 100), updated_at = ?
                    WHERE source_type = 'shop' AND is_active = 1
                    ''',
                    [percentage, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                )

                affected = cursor.rowcount
                conn.commit()

                print(f"✅ Updated prices for {affected} products by {percentage:+.1f}%")

            except ValueError:
                print("❌ Invalid percentage value.")

        elif choice == '2':
            # Update by category
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY category")
            categories = cursor.fetchall()

            if not categories:
                print("No categories found.")
                conn.close()
                return

            print("\nAvailable categories:")
            for i, cat in enumerate(categories):
                print(f"{i+1}. {cat['category']}")

            try:
                cat_choice = int(input("Select category: ").strip())
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return

                selected_category = categories[cat_choice-1]['category']
                percentage = float(input("Enter percentage change (+/-): ").strip())

                cursor.execute(
                    '''
                    UPDATE products
                    SET price = price * (1 + ? / 100), updated_at = ?
                    WHERE source_type = 'shop' AND category = ? AND is_active = 1
                    ''',
                    [percentage, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), selected_category]
                )

                affected = cursor.rowcount
                conn.commit()

                print(f"✅ Updated prices for {affected} products in '{selected_category}' by {percentage:+.1f}%")

            except (ValueError, IndexError):
                print("❌ Invalid input.")

        elif choice == '3':
            # Set fixed price for category
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY category")
            categories = cursor.fetchall()

            if not categories:
                print("No categories found.")
                conn.close()
                return

            print("\nAvailable categories:")
            for i, cat in enumerate(categories):
                print(f"{i+1}. {cat['category']}")

            try:
                cat_choice = int(input("Select category: ").strip())
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return

                selected_category = categories[cat_choice-1]['category']
                new_price = float(input("Enter new price (£): ").strip())

                if new_price < 0:
                    print("❌ Price cannot be negative.")
                    conn.close()
                    return

                cursor.execute(
                    '''
                    UPDATE products
                    SET price = ?, updated_at = ?
                    WHERE source_type = 'shop' AND category = ? AND is_active = 1
                    ''',
                    [new_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), selected_category]
                )

                affected = cursor.rowcount
                conn.commit()

                print(f"✅ Set price to £{new_price:.2f} for {affected} products in '{selected_category}'")

            except (ValueError, IndexError):
                print("❌ Invalid input.")

        else:
            print("❌ Invalid choice.")

        conn.close()
        input("\nPress Enter to continue...")

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        print(f"❌ Error updating prices: {e}")
