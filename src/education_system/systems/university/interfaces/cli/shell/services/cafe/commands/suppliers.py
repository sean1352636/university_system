from ..context import *  # noqa: F401,F403

def supplier_management_cli() -> None:
    """Supplier management submenu."""
    while True:
        print("\n--- Supplier Management ---")
        print("1. View All Suppliers")
        print("2. Add New Supplier")
        print("3. View Supplier Details")
        print("4. Update Supplier")
        print("5. Delete Supplier")
        print("6. Link Supplier to Menu Item")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            suppliers = get_all_suppliers()
            if not suppliers:
                print("\nNo suppliers found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Name':<25} {'Contact':<20} {'Email':<25} {'Phone':<15}")
            print(f"{'=' * 90}")
            for s in suppliers:
                sid, name, contact, email, phone, addr, terms = s
                print(f"{sid:<5} {(name or '')[:24]:<25} {(contact or 'N/A')[:19]:<20} {(email or 'N/A')[:24]:<25} {(phone or 'N/A')[:14]:<15}")
            print(f"\nTotal: {len(suppliers)} suppliers")
            input("\nPress Enter to continue...")

        elif choice == '2':
            print("\n--- Add New Supplier ---")
            name = input("Supplier name: ").strip()
            if not name:
                print("Name is required.")
                continue
            contact_person = input("Contact person (optional): ").strip()
            email = input("Email (optional): ").strip()
            phone = input("Phone (optional): ").strip()
            address = input("Address (optional): ").strip()
            payment_terms = input("Payment terms (e.g. Net 30, COD, optional): ").strip()

            supplier_id = add_supplier(name, contact_person, email, phone, address, payment_terms)
            if supplier_id:
                print(f"\n Supplier '{name}' added with ID: {supplier_id}")
            else:
                print("\n Failed to add supplier.")

        elif choice == '3':
            try:
                supplier_id = int(input("Enter Supplier ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            sid, name, contact, email, phone, address, terms = supplier
            print(f"\n{'=' * 50}")
            print(f"SUPPLIER DETAILS (ID: {sid})")
            print(f"{'=' * 50}")
            print(f"Name:           {name}")
            print(f"Contact Person: {contact or 'N/A'}")
            print(f"Email:          {email or 'N/A'}")
            print(f"Phone:          {phone or 'N/A'}")
            print(f"Address:        {address or 'N/A'}")
            print(f"Payment Terms:  {terms or 'N/A'}")

            # Show linked products
            products = get_supplier_products(supplier_id)
            if products:
                print("\nLinked Menu Items:")
                print(f"  {'ID':<5} {'Item':<25} {'Category':<15} {'Cost/Unit':<10}")
                print(f"  {'-' * 55}")
                for pid, pname, pcat, cost, pnotes in products:
                    cost_str = f"£{cost:.2f}" if cost else "N/A"
                    print(f"  {pid:<5} {pname[:24]:<25} {pcat:<15} {cost_str:<10}")
            else:
                print("\nNo menu items linked to this supplier.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                supplier_id = int(input("Enter Supplier ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            sid, name, contact, email, phone, address, terms = supplier
            print(f"\nUpdating: {name}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Name [{name}]: ").strip() or name
            new_contact = input(f"Contact [{contact or ''}]: ").strip() or contact
            new_email = input(f"Email [{email or ''}]: ").strip() or email
            new_phone = input(f"Phone [{phone or ''}]: ").strip() or phone
            new_address = input(f"Address [{address or ''}]: ").strip() or address
            new_terms = input(f"Payment Terms [{terms or ''}]: ").strip() or terms

            if update_supplier(supplier_id, new_name, new_contact, new_email, new_phone, new_address, new_terms):
                print(f"\n Supplier '{new_name}' updated!")
            else:
                print("\n Failed to update supplier.")

        elif choice == '5':
            try:
                supplier_id = int(input("Enter Supplier ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            confirm = input(f"Delete supplier '{supplier[1]}'? This also removes product links. (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_supplier(supplier_id):
                    print(f"\n Supplier '{supplier[1]}' deleted!")
                else:
                    print("\n Failed to delete supplier.")

        elif choice == '6':
            # Link supplier to menu item
            try:
                supplier_id = int(input("Enter Supplier ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            items = get_all_menu_items()
            if not items:
                print("No menu items available.")
                continue

            print(f"\n{'ID':<5} {'Item':<25} {'Category':<15}")
            print("-" * 45)
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                print(f"{item_id:<5} {name[:24]:<25} {cat:<15}")

            try:
                product_id = int(input("\nEnter Item ID to link: "))
            except ValueError:
                print("Invalid ID.")
                continue

            cost_input = input("Cost per unit from this supplier (optional, press Enter to skip): ").strip()
            cost = float(cost_input) if cost_input else None
            notes = input("Notes (optional): ").strip()

            if link_supplier_to_product(supplier_id, product_id, cost, notes):
                print(f"\n Supplier '{supplier[1]}' linked to item #{product_id}!")
            else:
                print("\n Failed to link supplier to item.")

        elif choice == '7':
            break

