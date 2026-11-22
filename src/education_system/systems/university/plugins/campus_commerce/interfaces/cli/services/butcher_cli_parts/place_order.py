"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def place_order():
    """Place a new order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to place orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Place New Order")

        # Show available products
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, name, category, price_per_unit, stock_quantity
                FROM products
                WHERE source_type = 'butcher' AND status = 'available' AND stock_quantity > 0
                ORDER BY category, name
            ''')
            products = cursor.fetchall()

            if not products:
                print("\n❌ No products available for order")
                input("\nPress Enter to continue...")
                return

            print("\n🥩 AVAILABLE PRODUCTS:")
            print("-" * 80)
            current_category = None
            for product in products:
                prod_id, name, category, price, stock = product
                if category != current_category:
                    print(f"\n📦 {category}:")
                    current_category = category

                stock_icon = get_stock_status_icon(float(stock))
                print(f"  {stock_icon} ID {prod_id}: {name} - {format_currency(float(price))}/kg (Stock: {float(stock):.2f}kg)")

        cart = []
        total = 0.0

        print("\n🛒 BUILD YOUR ORDER:")
        print("(Enter product ID and quantity, or 0 to finish)")

        while True:
            print(f"\n{'─' * 80}")
            print("📦 Current Cart:")
            if not cart:
                print("  (empty)")
            else:
                for idx, item in enumerate(cart, 1):
                    print(f"  {idx}. {item['name']} - {item['quantity']:.2f}kg @ {format_currency(item['price'])}/kg = {format_currency(item['subtotal'])}")
                print(f"\n  💰 Total: {format_currency(total)}")

            choice = input("\nEnter product ID (0 to finish, -1 to cancel): ").strip()

            if choice == "0":
                break
            elif choice == "-1":
                print("❌ Order cancelled")
                input("\nPress Enter to continue...")
                return

            if not choice.isdigit():
                print("❌ Invalid product ID")
                continue

            product_id = choice

            # Get product details
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT name, price_per_unit, stock_quantity, status
                    FROM products
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (product_id,))
                product = cursor.fetchone()

                if not product:
                    print("❌ Product not found")
                    continue

                name, price, stock, status = product

                if status != 'available':
                    print(f"❌ Product '{name}' is not available")
                    continue

                if float(stock) <= 0:
                    print(f"❌ Product '{name}' is out of stock")
                    continue

                # Get quantity with unit conversion
                print(f"\n📦 {name} - {format_currency(float(price))}/kg")
                print(f"   Available: {float(stock):.2f}kg")

                quantity_input = input("Enter quantity (e.g., '2.5 kg', '500 g', '1 lb'): ").strip()

                # Parse quantity and unit
                parts = quantity_input.split()
                if len(parts) == 1:
                    # No unit specified, assume kg
                    try:
                        quantity = float(parts[0])
                    except ValueError:
                        print("❌ Invalid quantity")
                        continue
                elif len(parts) == 2:
                    # Quantity and unit specified
                    try:
                        qty_value = float(parts[0])
                        qty_unit = parts[1]
                        quantity = convert_units(qty_value, qty_unit)
                        if quantity is None:
                            continue
                    except ValueError:
                        print("❌ Invalid quantity")
                        continue
                else:
                    print("❌ Invalid format. Use: '<number> <unit>' or just '<number>' for kg")
                    continue

                if quantity <= 0:
                    print("❌ Quantity must be greater than 0")
                    continue

                if quantity > float(stock):
                    print(f"❌ Insufficient stock. Available: {float(stock):.2f}kg")
                    continue

                subtotal = quantity * float(price)
                cart.append({
                    'product_id': product_id,
                    'name': name,
                    'quantity': quantity,
                    'price': float(price),
                    'subtotal': subtotal
                })
                total += subtotal
                print(f"✅ Added {quantity:.2f}kg of {name} to cart")

        if not cart:
            print("❌ Cart is empty. Order cancelled")
            input("\nPress Enter to continue...")
            return

        # Order summary and payment
        print_subheader("ORDER SUMMARY")
        for idx, item in enumerate(cart, 1):
            print(f"{idx}. {item['name']} - {item['quantity']:.2f}kg @ {format_currency(item['price'])}/kg = {format_currency(item['subtotal'])}")
        print(f"\n💰 Total: {format_currency(total)}")

        # Payment method
        print("\n💳 Payment Method:")
        print("1. Cash")
        print("2. Card")
        print("3. Student Finance Account")

        payment_choice = input("Select payment method (1-3): ").strip()

        payment_methods = {
            '1': 'cash',
            '2': 'card',
            '3': 'finance_account'
        }

        payment_method = payment_methods.get(payment_choice, 'cash')

        # Pickup date
        pickup_input = input("\nPickup date (YYYY-MM-DD, or press Enter for today): ").strip()
        if pickup_input:
            try:
                pickup_date = datetime.strptime(pickup_input, '%Y-%m-%d').date().isoformat()
            except ValueError:
                print("⚠️  Invalid date format. Using today.")
                pickup_date = datetime.now().date().isoformat()
        else:
            pickup_date = datetime.now().date().isoformat()

        # Order notes
        notes = input("Order notes (optional): ").strip()

        confirm = input("\n✅ Confirm order? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Order cancelled")
            input("\nPress Enter to continue...")
            return

        order_number = f"BO-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Process payment if using finance account
        if payment_method == 'finance_account' and FINANCE_AVAILABLE:
            try:
                charge = process_student_finance_account_payment(
                    student_id=str(user.get('student_id') or user.get('username')),
                    amount=total,
                    description='Butcher Shop Purchase',
                    transaction_source='Butcher Shop',
                    transaction_ref=order_number,
                    processed_by=user.get('username') or 'System',
                )
                if not charge.get('success'):
                    print(f"❌ Payment failed. {charge.get('message') or 'Insufficient funds or finance account error.'}")
                    input("\nPress Enter to continue...")
                    return
            except Exception as e:
                logger.error(f"Finance payment error: {e}")
                print(f"❌ Payment processing error: {e}")
                input("\nPress Enter to continue...")
                return

        # Create order

        with transaction() as conn:
            # Insert order
            conn.execute('''
                INSERT INTO orders
                (source_type, order_number, user_id, user_name, user_email, total_amount,
                 payment_method, order_status, order_date, pickup_date, notes)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (order_number, user.get('username'),
                  user.get('full_name', user.get('username')),
                  user.get('email', ''), total, payment_method,
                  datetime.now().isoformat(), pickup_date, notes))

            order_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Insert order items and update stock
            for item in cart:
                conn.execute('''
                    INSERT INTO order_items
                    (source_type, order_id, product_id, item_name, quantity_kg, unit_price, subtotal)
                    VALUES ('butcher', ?, ?, ?, ?, ?, ?)
                ''', (order_id, item['product_id'], item['name'], item['quantity'],
                      item['price'], item['subtotal']))

                # Update stock
                conn.execute('''
                    UPDATE products
                    SET stock_quantity = stock_quantity - ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (item['quantity'], item['product_id']))

                # Check if stock is now below reorder point
                cursor = conn.execute('''
                    SELECT stock_quantity, min_stock_level, name
                    FROM products
                    WHERE source_product_id = ? AND source_type = 'butcher' AND stock_quantity <= min_stock_level
                ''', (item['product_id'],))

                low_stock = cursor.fetchone()
                if low_stock:
                    # Create stock alert
                    conn.execute('''
                        INSERT INTO butcher_stock_alerts
                        (product_id, alert_type, alert_date)
                        VALUES (?, 'low_stock', ?)
                    ''', (item['product_id'], datetime.now().isoformat()))

        # Record to finance system
        if FINANCE_AVAILABLE and payment_method != 'finance_account':
            try:
                record_payment_to_finance(
                    user.get('username'),
                    total,
                    payment_method,
                    'Butcher Shop',
                    order_number
                )
            except Exception as e:
                logger.error(f"Error recording payment to finance: {e}")

        print("\n✅ Order placed successfully!")
        print(f"📝 Order Number: {order_number}")
        print(f"📅 Pickup Date: {pickup_date}")
        print(f"💰 Total: {format_currency(total)}")
        print(f"💳 Payment: {payment_method.replace('_', ' ').title()}")

        logger.info(f"User {user.get('username')} placed butcher order {order_number} for {format_currency(total)}")

        # Send email confirmation if available
        if EMAIL_AVAILABLE and user.get('email'):
            try:
                send_email(
                    user.get('email'),
                    'Butcher Shop Order Confirmation',
                    f"Your order {order_number} has been confirmed. Total: {format_currency(total)}. Pickup: {pickup_date}."
                )
            except Exception as e:
                logger.error(f"Error sending order confirmation email: {e}")

    except Exception as e:
        logger.error(f"Error placing order: {e}")
        print(f"❌ Error placing order: {e}")

    input("\nPress Enter to continue...")
