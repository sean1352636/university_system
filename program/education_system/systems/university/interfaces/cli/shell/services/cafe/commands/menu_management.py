from ..context import *  # noqa: F401,F403

def menu_management_cli() -> None:
    """Menu management submenu."""
    while True:
        print("\n--- Menu Management ---")
        print("1. View All Items")
        print("2. Add New Item")
        print("3. Edit Item")
        print("4. Delete Item")
        print("5. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            items = get_all_menu_items()
            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Item':<25} {'Category':<12} {'Price':<10} {'Stock':<8} {'Available':<10}")
            print(f"{'=' * 90}")
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                avail_str = "Yes" if available else "No"
                print(f"{item_id:<5} {name[:24]:<25} {cat:<12} £{price:<9.2f} {stock:<8} {avail_str:<10}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            # Add new item
            print("\n--- Add New Menu Item ---")
            name = input("Item name: ").strip()
            if not name:
                print("Name is required.")
                continue

            print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            try:
                cat_choice = int(input("Select category: "))
                category = CATEGORIES[cat_choice - 1] if 1 <= cat_choice <= len(CATEGORIES) else "Food"
            except (ValueError, IndexError):
                category = "Food"

            description = input("Description: ").strip()

            try:
                price = float(input("Price (£): "))
                stock = int(input("Initial stock: "))
            except ValueError:
                print("Invalid price or stock.")
                continue

            if add_menu_item(name, category, description, price, stock):
                print(f"\n Item '{name}' added successfully!")
            else:
                print("\n Failed to add item.")

        elif choice == '3':
            # Edit item
            try:
                item_id = int(input("Enter Item ID to edit: "))
            except ValueError:
                print("Invalid ID.")
                continue

            item = get_menu_item(item_id)
            if not item:
                print("Item not found.")
                continue

            item_id, name, cat, desc, price, available, stock = item
            print(f"\nEditing: {name}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Name [{name}]: ").strip() or name

            print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            cat_input = input(f"Category [{cat}]: ").strip()
            try:
                new_cat = CATEGORIES[int(cat_input) - 1] if cat_input else cat
            except (ValueError, IndexError):
                new_cat = cat

            price_input = input(f"Price [{price:.2f}]: ").strip()
            new_price = float(price_input) if price_input else price

            stock_input = input(f"Stock [{stock}]: ").strip()
            new_stock = int(stock_input) if stock_input else stock

            avail_input = input(f"Available [{'Y' if available else 'N'}] (Y/N): ").strip().upper()
            new_available = avail_input == 'Y' if avail_input else bool(available)

            if update_menu_item(item_id, new_name, new_cat, new_price, new_stock, new_available):
                print("\n Item updated successfully!")
            else:
                print("\n Failed to update item.")

        elif choice == '4':
            # Delete item
            try:
                item_id = int(input("Enter Item ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            item = get_menu_item(item_id)
            if not item:
                print("Item not found.")
                continue

            confirm = input(f"Delete '{item[1]}'? (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_menu_item(item_id):
                    print(f"\n Item '{item[1]}' deleted!")
                else:
                    print("\n Failed to delete item.")

        elif choice == '5':
            break

