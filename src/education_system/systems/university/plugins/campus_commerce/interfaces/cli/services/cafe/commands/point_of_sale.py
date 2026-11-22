from ..context import *  # noqa: F401,F403
# The domain service completes the sale (account debit + local write +
# Finance posting); it shadows the persistence-layer create_order above.
from education_system.systems.university.plugins.campus_commerce.domain.cafe.services.checkout import (
    create_order,
)

def point_of_sale_cli() -> None:
    """Process a new order via CLI."""
    print("\n" + "=" * 60)
    print("              NEW ORDER")
    print("=" * 60)

    # Get customer info
    student_id = input("Student ID (press Enter to skip): ").strip()
    customer_name = input("Customer Name (press Enter for Walk-in): ").strip() or "Walk-in Customer"

    # Current order items
    order_items = []
    total = 0.0

    while True:
        print("\n--- Order Items ---")
        if order_items:
            print(f"\n{'Item':<25} {'Qty':<5} {'Price':<10} {'Subtotal':<10}")
            print("-" * 55)
            for item in order_items:
                print(f"{item['name'][:24]:<25} {item['quantity']:<5} £{item['price']:<9.2f} £{item['subtotal']:<9.2f}")
            print("-" * 55)
            print(f"{'TOTAL:':<42} £{total:.2f}")
        else:
            print("No items in order.")

        print("\n1. Add Item")
        print("2. Remove Item")
        print("3. Complete Order")
        print("4. Cancel Order")

        action = input("\nSelect action: ").strip()

        if action == '1':
            # Add item
            items = get_all_menu_items(available_only=True)
            if not items:
                print("No items available.")
                continue

            print(f"\n{'ID':<5} {'Item':<25} {'Price':<10} {'Stock':<8}")
            print("-" * 50)
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                if stock > 0:
                    print(f"{item_id:<5} {name[:24]:<25} £{price:<9.2f} {stock:<8}")

            try:
                item_id = int(input("\nEnter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                item_id, name, cat, desc, price, available, stock = item
                if stock <= 0:
                    print(f"'{name}' is out of stock.")
                    continue

                quantity = int(input(f"Quantity (available: {stock}): "))
                if quantity < 1 or quantity > stock:
                    print("Invalid quantity.")
                    continue

                # Check if item already in order
                existing = next((i for i in order_items if i['item_id'] == item_id), None)
                if existing:
                    existing['quantity'] += quantity
                    existing['subtotal'] = existing['quantity'] * existing['price']
                else:
                    order_items.append({
                        'item_id': item_id,
                        'name': name,
                        'price': price,
                        'quantity': quantity,
                        'subtotal': price * quantity
                    })

                total = sum(i['subtotal'] for i in order_items)
                print(f"\nAdded {quantity} x {name}")

            except ValueError:
                print("Invalid input.")

        elif action == '2':
            # Remove item
            if not order_items:
                print("No items to remove.")
                continue

            print("\nSelect item to remove:")
            for i, item in enumerate(order_items, 1):
                print(f"{i}. {item['name']} (x{item['quantity']})")

            try:
                idx = int(input("Enter number: ")) - 1
                if 0 <= idx < len(order_items):
                    removed = order_items.pop(idx)
                    total = sum(i['subtotal'] for i in order_items)
                    print(f"Removed {removed['name']}")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")

        elif action == '3':
            # Complete order
            if not order_items:
                print("Cannot complete empty order.")
                continue

            print("\n--- Payment ---")
            print(f"Total: £{total:.2f}")
            print("\nPayment Method:")
            print("1. Student Account")
            print("2. Cash")
            print("3. Card")

            pay_choice = input("Select payment method: ").strip()

            payment_method = None
            if pay_choice == '1':
                payment_method = 'student_account'
                if not student_id:
                    student_id = input("Enter Student ID for payment: ").strip()
                    if not student_id:
                        print("Student ID required for student account payment.")
                        continue

                if FINANCE_ACCOUNT_AVAILABLE:
                    balance = get_student_finance_account_balance(student_id)
                    if balance is None:
                        print(f"No finance account found for {student_id}.")
                        continue
                    if balance < total:
                        print(f"Insufficient balance. Current balance: £{balance:.2f}")
                        continue
                else:
                    print("Student finance integration not available.")
                    continue

            elif pay_choice == '2':
                payment_method = 'cash'
            elif pay_choice == '3':
                payment_method = 'card'
            else:
                print("Invalid payment method.")
                continue

            # Create order (the domain service debits the student account
            # for student_account sales and posts the sale to Finance).
            order_id = create_order(student_id, customer_name, order_items, payment_method)
            if order_id:
                print(f"\n{'=' * 40}")
                print(f"ORDER #{order_id} COMPLETE")
                print(f"Total: £{total:.2f}")
                print(f"Payment: {payment_method}")
                print(f"{'=' * 40}")
            else:
                print("Failed to create order.")

            input("\nPress Enter to continue...")
            return

        elif action == '4':
            confirm = input("Cancel order? (y/n): ").strip().lower()
            if confirm == 'y':
                print("Order cancelled.")
                return

