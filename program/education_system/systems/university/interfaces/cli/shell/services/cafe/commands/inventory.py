from ..context import *  # noqa: F401,F403

def inventory_management_cli() -> None:
    """Inventory management submenu."""
    while True:
        print("\n--- Inventory Management ---")
        print("1. View Current Stock")
        print("2. Add Stock")
        print("3. Remove Stock")
        print("4. View Transactions")
        print("5. Low Stock Alert")
        print("6. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            items = get_all_menu_items()
            print(f"\n{'=' * 70}")
            print(f"{'ID':<5} {'Item':<30} {'Category':<15} {'Stock':<10} {'Status':<12}")
            print(f"{'=' * 70}")
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                if stock == 0:
                    status = "OUT OF STOCK"
                elif stock < 10:
                    status = "LOW"
                elif stock < 20:
                    status = "MODERATE"
                else:
                    status = "GOOD"
                print(f"{item_id:<5} {name[:29]:<30} {cat:<15} {stock:<10} {status:<12}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                item_id = int(input("Enter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                quantity = int(input(f"Quantity to add for '{item[1]}': "))
                if quantity < 1:
                    print("Invalid quantity.")
                    continue

                if update_stock(item_id, quantity, 'restock', 'Manual stock addition'):
                    print(f"\n Added {quantity} units to '{item[1]}'")
                else:
                    print("\n Failed to update stock.")
            except ValueError:
                print("Invalid input.")

        elif choice == '3':
            try:
                item_id = int(input("Enter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                current_stock = item[6]
                quantity = int(input(f"Quantity to remove from '{item[1]}' (current: {current_stock}): "))
                if quantity < 1 or quantity > current_stock:
                    print("Invalid quantity.")
                    continue

                if update_stock(item_id, -quantity, 'adjustment', 'Manual stock removal'):
                    print(f"\n Removed {quantity} units from '{item[1]}'")
                else:
                    print("\n Failed to update stock.")
            except ValueError:
                print("Invalid input.")

        elif choice == '4':
            transactions = get_inventory_transactions(50)
            if not transactions:
                print("\nNo transactions found.")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<6} {'Item':<25} {'Change':<10} {'Type':<12} {'Date':<20} {'Notes':<15}")
            print(f"{'=' * 90}")
            for trans in transactions:
                trans_id, name, change, trans_type, date, notes = trans
                change_str = f"+{change}" if change > 0 else str(change)
                print(f"{trans_id:<6} {name[:24]:<25} {change_str:<10} {trans_type:<12} {str(date)[:19]:<20} {(notes or '')[:14]:<15}")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = get_low_stock_items(20)
            if not items:
                print("\nAll items have adequate stock.")
            else:
                print(f"\n{'=' * 50}")
                print("LOW STOCK ALERT")
                print(f"{'=' * 50}")
                for name, cat, stock in items:
                    status = "OUT OF STOCK" if stock == 0 else "LOW STOCK"
                    print(f"[{status}] {name} ({cat}): {stock} units")
            input("\nPress Enter to continue...")

        elif choice == '6':
            break

