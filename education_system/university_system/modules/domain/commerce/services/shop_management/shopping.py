import time
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_read, log_create
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.domain.commerce.services.shop_management import config


@log_read(module="shop", description="Browsing products")
def browse_products():
    """Display all available products for browsing"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to browse products.")
        return

    if not config.auth.check_permission('view_products'):
        print("You don't have permission to view products.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        cursor = conn.cursor()

        # Get filter options
        print("\nFilter options:")
        print("1. View all products")
        print("2. Filter by category")
        print("3. Filter by price range")
        print("4. Search by name")

        filter_choice = input("Enter your choice (1-4): ").strip()

        query_params = []
        if filter_choice == '1':
            # View all products
            query = '''
            SELECT p.*, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1
            ORDER BY p.category, p.name
            '''
        elif filter_choice == '2':
            # Filter by category
            # First get available categories
            cursor.execute(
                'SELECT DISTINCT category FROM products WHERE source_type = \'shop\' AND is_active = 1 ORDER BY category'
            )
            categories = cursor.fetchall()

            if not categories:
                print("No categories found.")
                conn.close()
                return

            print("\nAvailable categories:")
            for i, category in enumerate(categories):
                print(f"{i+1}. {category['category']}")

            try:
                cat_choice = int(input("Select a category number: "))
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return

                selected_category = categories[cat_choice-1]['category']
                query = '''
                SELECT p.*, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1 AND p.category = ?
                ORDER BY p.name
                '''
                query_params = [selected_category]
            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif filter_choice == '3':
            # Filter by price range
            try:
                min_price = float(input("Enter minimum price: ").strip() or 0)
                max_price = float(input("Enter maximum price: ").strip() or 1000000)

                if min_price < 0 or max_price < 0 or min_price > max_price:
                    print("Invalid price range.")
                    conn.close()
                    return

                query = '''
                SELECT p.*, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1 AND p.price BETWEEN ? AND ?
                ORDER BY p.price
                '''
                query_params = [min_price, max_price]
            except ValueError:
                print("Invalid input. Please enter numeric values for prices.")
                conn.close()
                return

        elif filter_choice == '4':
            # Search by name
            search_term = input("Enter product name to search: ").strip()
            if not search_term:
                print("Search term cannot be empty.")
                conn.close()
                return

            query = '''
            SELECT p.*, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND p.name LIKE ?
            ORDER BY p.name
            '''
            query_params = [f'%{search_term}%']

        else:
            print("Invalid choice. Showing all products.")
            query = '''
            SELECT p.*, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1
            ORDER BY p.category, p.name
            '''

        # Execute the query
        cursor.execute(query, query_params)
        products = cursor.fetchall()

        if not products:
            print("No products found matching your criteria.")
            conn.close()
            return

        # Display products
        print("\nProducts:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Category':<15} {'Stock':<8} {'Description'}")
        print("-" * 90)

        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            desc = product['description'] or ''
            print(f"{product['source_product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['category'][:13]:<15} {product['quantity']:<8} {desc[:30]}...")

        # Option to add to cart
        if config.auth.check_permission('make_purchase'):
            while True:
                add_to_cart = input("\nWould you like to add a product to your cart? (y/n): ").strip().lower()
                if add_to_cart == 'y':
                    product_id = input("Enter the product ID to add to cart: ").strip().upper()

                    # Check if product exists
                    cursor.execute(
                        '''
                        SELECT p.*, i.quantity
                        FROM products p
                        JOIN shop_inventory i ON p.source_product_id = i.product_id
                        WHERE p.source_type = 'shop' AND p.source_product_id = ? AND p.is_active = 1
                        ''',
                        [product_id]
                    )
                    product = cursor.fetchone()

                    if not product:
                        print("Product not found or not available.")
                        continue

                    try:
                        quantity = int(input(f"Enter quantity (available: {product['quantity']}): ").strip())
                        if quantity <= 0:
                            print("Quantity must be greater than 0.")
                            continue

                        if quantity > product['quantity']:
                            print(f"Insufficient stock. Only {product['quantity']} available.")
                            continue

                        # Add to cart
                        add_to_shopping_cart(product_id, quantity)
                    except ValueError:
                        print("Invalid quantity. Please enter a number.")
                        continue
                elif add_to_cart == 'n':
                    break
                else:
                    print("Invalid choice. Please enter 'y' or 'n'.")

        print("\nPress Enter to continue...")
        input()
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error browsing products: {e}")
        if 'conn' in locals():
            conn.close()

def add_to_shopping_cart(product_id, quantity):
    """Add a product to the user's shopping cart"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to add products to cart.")
        return False

    if not config.auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if product exists and has sufficient inventory
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, i.quantity
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.source_product_id = ? AND p.is_active = 1
            ''',
            [product_id]
        )
        product = cursor.fetchone()

        if not product:
            print("Product not found or not available.")
            conn.close()
            return False

        if quantity > product[1]:
            print(f"Insufficient stock. Only {product[1]} available.")
            conn.close()
            return False

        # Check if product already in cart
        cursor.execute(
            '''
            SELECT quantity FROM cart
            WHERE source_type = 'shop' AND user_id = ? AND product_id = ?
            ''',
            [config.auth.current_user['id'], product_id]
        )
        cart_item = cursor.fetchone()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if cart_item:
            # Update quantity if already in cart
            new_quantity = cart_item[0] + quantity
            cursor.execute(
                '''
                UPDATE cart
                SET quantity = ?, added_at = ?
                WHERE source_type = 'shop' AND user_id = ? AND product_id = ?
                ''',
                [new_quantity, now, config.auth.current_user['id'], product_id]
            )
            print(f"Updated cart: {product_id} (quantity: {new_quantity})")
        else:
            # Add new item to cart
            cursor.execute(
                '''
                INSERT INTO cart (source_type, user_id, product_id, quantity, added_at)
                VALUES ('shop', ?, ?, ?, ?)
                ''',
                [config.auth.current_user['id'], product_id, quantity, now]
            )
            print(f"Added to cart: {product_id} (quantity: {quantity})")

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"Database error adding to cart: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Error adding to cart: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="shop", description="Viewing shopping cart")
def view_shopping_cart():
    """View the current user's shopping cart"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view your shopping cart.")
        return

    if not config.auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get cart items with product details
        cursor.execute(
            '''
            SELECT c.cart_id, c.product_id, p.name, p.price, c.quantity,
                   p.price * c.quantity AS subtotal
            FROM cart c
            JOIN products p ON c.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE c.source_type = 'shop' AND c.user_id = ?
            ORDER BY c.added_at DESC
            ''',
            [config.auth.current_user['id']]
        )

        cart_items = cursor.fetchall()

        if not cart_items:
            print("\nYour shopping cart is empty.")
            conn.close()
            return

        # Display cart items
        print("\nYour Shopping Cart:")
        print(f"{'ID':<8} {'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
        print("-" * 70)

        total = 0
        for item in cart_items:
            price_formatted = f"£{item['price']:.2f}"
            subtotal_formatted = f"£{item['subtotal']:.2f}"
            print(f"{item['product_id']:<8} {item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            total += item['subtotal']

        print("-" * 70)
        print(f"Total: £{total:.2f}")

        # Cart management options
        while True:
            print("\nCart Options:")
            print("1. Update item quantity")
            print("2. Remove item from cart")
            print("3. Empty cart")
            print("4. Proceed to checkout")
            print("5. Return to shop menu")

            choice = input("Enter your choice (1-5): ").strip()

            if choice == '1':
                # Update quantity
                product_id = input("Enter product ID to update: ").strip().upper()

                # Check if product in cart
                cursor.execute(
                    "SELECT cart_id FROM cart WHERE source_type = 'shop' AND user_id = ? AND product_id = ?",
                    [config.auth.current_user['id'], product_id]
                )

                if not cursor.fetchone():
                    print(f"Product {product_id} not found in your cart.")
                    continue

                try:
                    new_quantity = int(input("Enter new quantity: ").strip())
                    if new_quantity <= 0:
                        print("Invalid quantity. Use 'Remove item' to remove from cart.")
                        continue

                    # Check inventory
                    cursor.execute(
                        "SELECT quantity FROM shop_inventory WHERE product_id = ?",
                        [product_id]
                    )
                    available = cursor.fetchone()['quantity']

                    if new_quantity > available:
                        print(f"Cannot update: only {available} available in stock.")
                        continue

                    # Update quantity
                    cursor.execute(
                        '''
                        UPDATE cart
                        SET quantity = ?, added_at = ?
                        WHERE source_type = 'shop' AND user_id = ? AND product_id = ?
                        ''',
                        [new_quantity, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                         config.auth.current_user['id'], product_id]
                    )

                    conn.commit()
                    print(f"Updated quantity for {product_id} to {new_quantity}.")

                    # Refresh cart view
                    view_shopping_cart()
                    return

                except ValueError:
                    print("Invalid quantity. Please enter a number.")

            elif choice == '2':
                # Remove item
                product_id = input("Enter product ID to remove: ").strip().upper()

                cursor.execute(
                    "DELETE FROM cart WHERE source_type = 'shop' AND user_id = ? AND product_id = ?",
                    [config.auth.current_user['id'], product_id]
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"Removed {product_id} from cart.")

                    # Refresh cart view
                    view_shopping_cart()
                    return
                else:
                    print(f"Product {product_id} not found in your cart.")

            elif choice == '3':
                # Empty cart
                confirm = input("Are you sure you want to empty your cart? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute(
                        "DELETE FROM cart WHERE source_type = 'shop' AND user_id = ?",
                        [config.auth.current_user['id']]
                    )
                    conn.commit()
                    print("Cart emptied successfully.")
                    conn.close()
                    return

            elif choice == '4':
                # Proceed to checkout
                conn.close()
                checkout_process()
                return

            elif choice == '5':
                # Return to shop menu
                conn.close()
                return

            else:
                print("Invalid choice. Please try again.")

    except sqlite3.Error as e:
        print(f"Database error viewing cart: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing cart: {e}")
        if 'conn' in locals():
            conn.close()

@log_create(module="shop", description="Processing checkout")
def checkout_process():
    """Process the checkout for items in the shopping cart"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to checkout.")
        return

    if not config.auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get cart items with product details
        cursor.execute(
            '''
            SELECT c.cart_id, c.product_id, p.name, p.price, c.quantity,
                   p.price * c.quantity AS subtotal,
                   i.quantity AS available_stock
            FROM cart c
            JOIN products p ON c.product_id = p.source_product_id AND p.source_type = 'shop'
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE c.source_type = 'shop'
            AND c.user_id = ?
            ''',
            [config.auth.current_user['id']]
        )

        cart_items = cursor.fetchall()

        if not cart_items:
            print("\nYour shopping cart is empty. Nothing to checkout.")
            conn.close()
            return

        # Check stock availability
        out_of_stock_items = []
        for item in cart_items:
            if item['quantity'] > item['available_stock']:
                out_of_stock_items.append((item['product_id'], item['name'], item['available_stock']))

        if out_of_stock_items:
            print("\nSome items in your cart are no longer available in the requested quantity:")
            for product_id, name, available in out_of_stock_items:
                print(f"- {name} (ID: {product_id}): Only {available} available")

            print("\nPlease update your cart before proceeding with checkout.")
            conn.close()
            return

        # Display order summary
        print("\nOrder Summary:")
        print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
        print("-" * 70)

        total = 0
        for item in cart_items:
            price_formatted = f"£{item['price']:.2f}"
            subtotal_formatted = f"£{item['subtotal']:.2f}"
            print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            total += item['subtotal']

        print("-" * 70)
        print(f"Total: £{total:.2f}")

        # Get student ID if available
        student_id = None
        cursor.execute(
            "SELECT student_id FROM users WHERE id = ?",
            [config.auth.current_user['id']]
        )
        user_data = cursor.fetchone()
        if user_data and user_data['student_id']:
            student_id = user_data['student_id']

            # Check for student discount
            cursor.execute(
                '''
                SELECT * FROM shop_discounts
                WHERE name = 'Student Discount' AND is_active = 1
                AND (end_date IS NULL OR end_date > ?)
                ''',
                [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            )
            student_discount = cursor.fetchone()

            if student_discount:
                discount_value = student_discount['discount_value']
                discount_amount = total * (discount_value / 100)
                discounted_total = total - discount_amount

                print(f"Student Discount ({discount_value}%): -£{discount_amount:.2f}")
                print(f"Discounted Total: £{discounted_total:.2f}")
                total = discounted_total

        # Confirm purchase
        confirm = input("\nConfirm purchase? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Checkout cancelled.")
            conn.close()
            return

        # Get payment method
        print("\nPayment Methods:")
        print("1. Credit/Debit Card")
        print("2. Student Account")
        print("3. PayPal")

        payment_method = None
        while not payment_method:
            choice = input("Select payment method (1-3): ").strip()
            if choice == '1':
                payment_method = "Credit/Debit Card"
            elif choice == '2':
                if not student_id:
                    print("Student Account payment is only available for students.")
                    continue
                payment_method = "Student Account"
            elif choice == '3':
                payment_method = "PayPal"
            else:
                print("Invalid choice. Please select a valid payment method.")

        # Generate transaction ID
        transaction_id = f"T{int(time.time())}"
        transaction_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create transaction record
        cursor.execute(
            '''
            INSERT INTO transactions
            (source_transaction_id, customer_id, student_id, total_amount, created_at, payment_method, status, notes, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'shop')
            ''',
            [transaction_id, config.auth.current_user['id'], student_id, total,
             transaction_date, payment_method, "Completed", None]
        )

        # Create transaction items (batch insert to avoid N+1)
        transaction_items_data = [
            (transaction_id, item['product_id'], item['quantity'],
             item['price'], item['price'] * item['quantity'])
            for item in cart_items
        ]
        cursor.executemany(
            '''
            INSERT INTO shop_transaction_items
            (transaction_id, product_id, quantity, price_per_item, subtotal)
            VALUES (?, ?, ?, ?, ?)
            ''',
            transaction_items_data
        )

        # Update inventory (batch update to avoid N+1)
        inventory_update_data = [
            (item['quantity'], item['product_id'])
            for item in cart_items
        ]
        cursor.executemany(
            '''
            UPDATE shop_inventory
            SET quantity = quantity - ?
            WHERE product_id = ?
            ''',
            inventory_update_data
        )

        # Clear shopping cart
        cursor.execute(
            "DELETE FROM cart WHERE source_type = 'shop' AND user_id = ?",
            [config.auth.current_user['id']]
        )

        conn.commit()

        # Record transaction to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id=student_id or "EXTERNAL",
            amount=total,
            payment_method=payment_method,
            transaction_source='Shop',
            transaction_ref=transaction_id,
            notes=f'Shop purchase: {len(cart_items)} item(s)',
            created_by=config.auth.current_user['username'] if config.auth and config.auth.current_user else None
        )

        # Display confirmation
        print("\nOrder placed successfully!")
        print(f"Transaction ID: {transaction_id}")
        print(f"Total Amount: £{total:.2f}")
        print(f"Date: {transaction_date}")
        print(f"Payment Method: {payment_method}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")
        print("\nThank you for your purchase!")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error during checkout: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error during checkout: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_read(module="shop", description="Viewing purchase history")
def view_purchase_history():
    """View the user's purchase history"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view purchase history.")
        return

    if not config.auth.check_permission('view_own_purchase_history'):
        print("You don't have permission to view purchase history.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get transactions for the current user
        cursor.execute(
            '''
            SELECT * FROM transactions
            WHERE source_type = 'shop' AND customer_id = ?
            ORDER BY created_at DESC
            ''',
            [config.auth.current_user['id']]
        )

        transactions = cursor.fetchall()

        if not transactions:
            print("\nYou haven't made any purchases yet.")
            conn.close()
            return

        # Display transactions
        print("\nYour Purchase History:")
        print(f"{'Transaction ID':<20} {'Date':<20} {'Total':<12} {'Payment Method':<20} {'Status'}")
        print("-" * 85)

        for transaction in transactions:
            total_formatted = f"£{transaction['total_amount']:.2f}"
            date_formatted = transaction['created_at']
            print(f"{transaction['source_transaction_id']:<20} {date_formatted:<20} {total_formatted:<12} {transaction['payment_method']:<20} {transaction['status']}")

        # Option to view transaction details
        while True:
            transaction_id = input("\nEnter transaction ID to view details (or 'back' to return): ").strip()

            if transaction_id.lower() == 'back':
                break

            # Check if transaction belongs to user
            cursor.execute(
                '''
                SELECT * FROM transactions
                WHERE source_type = 'shop' AND source_transaction_id = ? AND customer_id = ?
                ''',
                [transaction_id, config.auth.current_user['id']]
            )

            transaction = cursor.fetchone()

            if not transaction:
                print("Transaction not found or not authorized to view.")
                continue

            # Get transaction items
            cursor.execute(
                '''
                SELECT i.*, p.name
                FROM shop_transaction_items i
                JOIN products p ON i.product_id = p.source_product_id AND p.source_type = 'shop'
                WHERE i.transaction_id = ?
                ''',
                [transaction_id]
            )

            items = cursor.fetchall()

            # Display transaction details
            print(f"\nTransaction Details - {transaction_id}")
            print(f"Date: {transaction['created_at']}")
            print(f"Status: {transaction['status']}")
            print(f"Payment Method: {transaction['payment_method']}")

            print("\nItems:")
            print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
            print("-" * 70)

            for item in items:
                price_formatted = f"£{item['price_per_item']:.2f}"
                subtotal_formatted = f"£{item['subtotal']:.2f}"
                print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")

            print("-" * 70)
            print(f"Total: £{transaction['total_amount']:.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error viewing purchase history: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing purchase history: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Viewing all transactions")
def view_all_transactions():
    """View all shop transactions (admin function)"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view transactions.")
        return

    if not config.auth.check_permission('view_all_transactions'):
        print("You don't have permission to view all transactions.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get filter options
        print("\nFilter options:")
        print("1. All transactions")
        print("2. By date range")
        print("3. By payment method")
        print("4. By student ID")
        print("5. By minimum amount")

        filter_choice = input("Enter your choice (1-5): ").strip()

        query_params = []
        base_query = '''
        SELECT t.*, u.username
        FROM transactions t
        LEFT JOIN users u ON t.customer_id = u.id
        WHERE t.source_type = 'shop'
        '''

        if filter_choice == '1':
            # All transactions
            query = base_query + ' ORDER BY t.created_at DESC'
        elif filter_choice == '2':
            # By date range
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()

            try:
                # Validate dates
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')

                # Add time to make it a full day range
                start_date = start.strftime('%Y-%m-%d 00:00:00')
                end_date = end.strftime('%Y-%m-%d 23:59:59')

                query = base_query + ' AND t.created_at BETWEEN ? AND ? ORDER BY t.created_at DESC'
                query_params = [start_date, end_date]
            except ValueError:
                print("Invalid date format. Using all transactions.")
                query = base_query + ' ORDER BY t.created_at DESC'

        elif filter_choice == '3':
            # By payment method
            print("\nPayment Methods:")
            print("1. Credit/Debit Card")
            print("2. Student Account")
            print("3. PayPal")

            method_choice = input("Select payment method (1-3): ").strip()

            if method_choice == '1':
                payment_method = "Credit/Debit Card"
            elif method_choice == '2':
                payment_method = "Student Account"
            elif method_choice == '3':
                payment_method = "PayPal"
            else:
                print("Invalid choice. Using all transactions.")
                query = base_query + ' ORDER BY t.created_at DESC'
                payment_method = None

            if payment_method:
                query = base_query + ' AND t.payment_method = ? ORDER BY t.created_at DESC'
                query_params = [payment_method]

        elif filter_choice == '4':
            # By student ID
            student_id = input("Enter student ID: ").strip()

            if student_id:
                query = base_query + ' AND t.student_id = ? ORDER BY t.created_at DESC'
                query_params = [student_id]
            else:
                print("Invalid student ID. Using all transactions.")
                query = base_query + ' ORDER BY t.created_at DESC'

        elif filter_choice == '5':
            # By minimum amount
            try:
                min_amount = float(input("Enter minimum amount: ").strip())

                query = base_query + ' AND t.total_amount >= ? ORDER BY t.total_amount DESC'
                query_params = [min_amount]
            except ValueError:
                print("Invalid amount. Using all transactions.")
                query = base_query + ' ORDER BY t.created_at DESC'

        else:
            print("Invalid choice. Using all transactions.")
            query = base_query + ' ORDER BY t.created_at DESC'

        # Execute the query
        cursor.execute(query, query_params)
        transactions = cursor.fetchall()

        if not transactions:
            print("\nNo transactions found matching your criteria.")
            conn.close()
            return

        # Display transactions
        print("\nTransaction List:")
        print(f"{'ID':<12} {'User':<15} {'Student ID':<12} {'Date':<20} {'Amount':<10} {'Payment Method':<20} {'Status'}")
        print("-" * 100)

        for transaction in transactions:
            amount_formatted = f"£{transaction['total_amount']:.2f}"
            date_formatted = transaction['created_at']
            username = transaction['username'] or 'Unknown'
            student_id = transaction['student_id'] or 'N/A'

            print(f"{transaction['source_transaction_id']:<12} {username[:13]:<15} {student_id:<12} {date_formatted:<20} {amount_formatted:<10} {transaction['payment_method']:<20} {transaction['status']}")

        print(f"\nTotal Transactions: {len(transactions)}")

        # Sum of all amounts
        total_value = sum(t['total_amount'] for t in transactions)
        print(f"Total Value: £{total_value:.2f}")

        # Option to view transaction details
        while True:
            transaction_id = input("\nEnter transaction ID to view details (or 'back' to return): ").strip()

            if transaction_id.lower() == 'back':
                break

            # Check if transaction exists
            cursor.execute(
                '''
                SELECT t.*, u.username, u.email
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND t.source_transaction_id = ?
                ''',
                [transaction_id]
            )

            transaction = cursor.fetchone()

            if not transaction:
                print("Transaction not found.")
                continue

            # Get transaction items
            cursor.execute(
                '''
                SELECT i.*, p.name
                FROM shop_transaction_items i
                JOIN products p ON i.product_id = p.source_product_id AND p.source_type = 'shop'
                WHERE i.transaction_id = ?
                ''',
                [transaction_id]
            )

            items = cursor.fetchall()

            # Display transaction details
            print(f"\nTransaction Details - {transaction_id}")
            print(f"User: {transaction['username']} (ID: {transaction['customer_id']})")
            print(f"Email: {transaction['email']}")
            if transaction['student_id']:
                print(f"Student ID: {transaction['student_id']}")
            print(f"Date: {transaction['created_at']}")
            print(f"Status: {transaction['status']}")
            print(f"Payment Method: {transaction['payment_method']}")

            if transaction['notes']:
                print(f"Notes: {transaction['notes']}")

            print("\nItems:")
            print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
            print("-" * 70)

            for item in items:
                price_formatted = f"£{item['price_per_item']:.2f}"
                subtotal_formatted = f"£{item['subtotal']:.2f}"
                print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")

            print("-" * 70)
            print(f"Total: £{transaction['total_amount']:.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error viewing transactions: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing transactions: {e}")
        if 'conn' in locals():
            conn.close()

# Product Management Functions
def validate_inventory_before_checkout(cart_items):
    """Validate that all cart items are still available in sufficient quantity"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        validation_errors = []

        for item in cart_items:
            cursor.execute(
                '''
                SELECT i.quantity, p.name, p.is_active
                FROM shop_inventory i
                JOIN products p ON i.product_id = p.source_product_id AND p.source_type = 'shop'
                WHERE p.source_product_id = ?
                ''',
                [item['product_id']]
            )

            result = cursor.fetchone()

            if not result:
                validation_errors.append(f"Product {item['product_id']} not found")
                continue

            if not result['is_active']:
                validation_errors.append(f"{result['name']} is no longer available")
                continue

            if result['quantity'] < item['quantity']:
                validation_errors.append(
                    f"{result['name']}: Only {result['quantity']} available, "
                    f"but {item['quantity']} requested"
                )

        conn.close()
        return validation_errors

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return [f"Validation error: {e}"]
