from ..context import *  # noqa: F401,F403
from education_system.systems.university.plugins.campus_commerce.domain.cafe.services.checkout import (
    refund_order,
)

def order_history_cli() -> None:
    """View order history."""
    while True:
        print("\n--- Order History ---")
        print("1. Today's Orders")
        print("2. This Week")
        print("3. This Month")
        print("4. All Orders")
        print("5. View Order Details")
        print("6. Refund an Order")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        filter_map = {'1': 'today', '2': 'week', '3': 'month', '4': 'all'}

        if choice in filter_map:
            orders = get_orders(filter_map[choice])
            if not orders:
                print("\nNo orders found.")
                continue

            print(f"\n{'=' * 100}")
            print(f"{'Order ID':<10} {'Date':<20} {'Customer':<20} {'Items':<8} {'Total':<12} {'Payment':<15} {'Status':<10}")
            print(f"{'=' * 100}")
            for order in orders:
                order_id, date, customer, items, total, payment, status = order
                print(f"{order_id:<10} {str(date)[:19]:<20} {customer[:19]:<20} {items:<8} £{total:<11.2f} {payment or 'N/A':<15} {status:<10}")
            print(f"\nTotal: {len(orders)} orders")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                order_id = int(input("Enter Order ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            items = get_order_items(order_id)
            if not items:
                print("Order not found or no items.")
                continue

            print(f"\n--- Order #{order_id} Details ---")
            print(f"{'Item':<30} {'Qty':<8} {'Price':<10} {'Subtotal':<10}")
            print("-" * 60)
            total = 0
            for item in items:
                name, qty, price, subtotal = item
                total += subtotal
                print(f"{name[:29]:<30} {qty:<8} £{price:<9.2f} £{subtotal:<9.2f}")
            print("-" * 60)
            print(f"{'Total:':<50} £{total:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            try:
                order_id = int(input("Enter Order ID to refund: "))
            except ValueError:
                print("Invalid ID.")
                continue
            items = get_order_items(order_id)
            if not items:
                print("Order not found or no items.")
                continue
            total = sum(item[3] for item in items)
            print(f"Order #{order_id} total: £{total:.2f}")
            print("Refund method:")
            print("1. Cash")
            print("2. Card")
            print("3. Student Account")
            method = {'1': 'Cash', '2': 'Card', '3': 'Student Account'}.get(
                input("Choice: ").strip(), 'Cash')
            student_id = None
            if method == 'Student Account':
                student_id = input("Student ID: ").strip() or None
            outcome = refund_order(order_id, total, method, student_id=student_id)
            print(outcome['message'])
            if outcome['success']:
                print(f"Refund reference: {outcome['refund_ref']}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            break

