"""
Equipment Rental CLI Interface

Command-line interface for equipment rental management including
inventory, rentals, returns, payments, and reporting.
"""

from datetime import datetime

from education_system.systems.university.domain.operations.campus.equipment.services.equipment_core import (
    init_equipment_db,
    EquipmentManager,
    RentalManager,
    TransactionManager,
    ReportManager,
    EQUIPMENT_CATEGORIES,
    EQUIPMENT_CONDITIONS,
    RENTAL_STATUSES,
)


def display_menu():
    """Display the equipment rental management menu and handle user input."""
    init_equipment_db()

    while True:
        print("\n" + "=" * 70)
        print(" " * 18 + "EQUIPMENT RENTAL MANAGEMENT SYSTEM")
        print("=" * 70)

        print("\n[Inventory]")
        print("1.  Add Equipment Item")
        print("2.  Update Equipment Item")
        print("3.  View Equipment Item")
        print("4.  List All Equipment")
        print("5.  List Available Equipment")

        print("\n[Rentals]")
        print("6.  Create Rental")
        print("7.  View Rental Details")
        print("8.  Check Out Equipment")
        print("9.  Return Equipment")
        print("10. Extend Rental")
        print("11. Cancel Rental")
        print("12. List Rentals by Status")

        print("\n[Payments]")
        print("13. Record Payment")
        print("14. Refund Deposit")
        print("15. View Transactions")

        print("\n[Reports]")
        print("16. Inventory Summary")
        print("17. Revenue Report")
        print("18. Popular Items")
        print("19. Overdue Rentals")
        print("20. Full Admin Report")

        print("\n0.  Back to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            if choice == "0":
                break
            elif choice == "1":
                _add_item()
            elif choice == "2":
                _update_item()
            elif choice == "3":
                _view_item()
            elif choice == "4":
                _list_all_items()
            elif choice == "5":
                _list_available_items()
            elif choice == "6":
                _create_rental()
            elif choice == "7":
                _view_rental()
            elif choice == "8":
                _checkout_item()
            elif choice == "9":
                _return_item()
            elif choice == "10":
                _extend_rental()
            elif choice == "11":
                _cancel_rental()
            elif choice == "12":
                _list_rentals_by_status()
            elif choice == "13":
                _record_payment()
            elif choice == "14":
                _refund_deposit()
            elif choice == "15":
                _view_transactions()
            elif choice == "16":
                _inventory_summary()
            elif choice == "17":
                _revenue_report()
            elif choice == "18":
                _popular_items()
            elif choice == "19":
                _overdue_rentals()
            elif choice == "20":
                _admin_report()
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")


def _add_item():
    """Add a new equipment item."""
    print("\n--- Add Equipment Item ---")
    item_code = input("Item code: ").strip()
    name = input("Name: ").strip()

    print(f"Categories: {', '.join(EQUIPMENT_CATEGORIES)}")
    category = input("Category: ").strip()
    if category not in EQUIPMENT_CATEGORIES:
        print("Invalid category.")
        return

    daily_rate = float(input("Daily rate: ").strip())
    description = input("Description (optional): ").strip() or None
    brand = input("Brand (optional): ").strip() or None
    model = input("Model (optional): ").strip() or None
    location = input("Location (optional): ").strip() or None
    qty_str = input("Quantity (default 1): ").strip()
    quantity = int(qty_str) if qty_str else 1

    item_id = EquipmentManager.add_item(
        item_code, name, category, daily_rate,
        description=description, brand=brand, model=model,
        location=location, quantity_total=quantity,
    )
    if item_id:
        print(f"Equipment item added successfully. Item ID: {item_id}")
    else:
        print("Failed to add equipment item.")


def _update_item():
    """Update an equipment item."""
    print("\n--- Update Equipment Item ---")
    item_id = int(input("Item ID: ").strip())

    item = EquipmentManager.get_item(item_id)
    if not item:
        print("Item not found.")
        return

    print(f"Current: {item['name']} | {item['category']} | Rate: {item['daily_rate']}")
    print("Press Enter to keep current value.")

    updates = {}
    name = input(f"Name [{item['name']}]: ").strip()
    if name:
        updates['name'] = name
    rate = input(f"Daily rate [{item['daily_rate']}]: ").strip()
    if rate:
        updates['daily_rate'] = float(rate)
    location = input(f"Location [{item.get('location', '')}]: ").strip()
    if location:
        updates['location'] = location

    print(f"Conditions: {', '.join(EQUIPMENT_CONDITIONS)}")
    condition = input(f"Condition [{item.get('condition', '')}]: ").strip()
    if condition:
        updates['condition'] = condition

    if updates:
        if EquipmentManager.update_item(item_id, **updates):
            print("Item updated successfully.")
        else:
            print("Failed to update item.")
    else:
        print("No changes made.")


def _view_item():
    """View equipment item details."""
    print("\n--- View Equipment Item ---")
    item_id = int(input("Item ID: ").strip())
    item = EquipmentManager.get_item(item_id)
    if not item:
        print("Item not found.")
        return
    print(f"\n  ID:          {item['item_id']}")
    print(f"  Code:        {item['item_code']}")
    print(f"  Name:        {item['name']}")
    print(f"  Category:    {item['category']}")
    print(f"  Brand:       {item.get('brand', 'N/A')}")
    print(f"  Model:       {item.get('model', 'N/A')}")
    print(f"  Daily Rate:  £{item['daily_rate']:.2f}")
    print(f"  Condition:   {item.get('condition', 'N/A')}")
    print(f"  Location:    {item.get('location', 'N/A')}")
    print(f"  Total Qty:   {item['quantity_total']}")
    print(f"  Available:   {item['quantity_available']}")
    print(f"  Active:      {'Yes' if item['is_active'] else 'No'}")


def _list_all_items():
    """List all equipment items."""
    print("\n--- All Equipment Items ---")
    items = EquipmentManager.get_all_items()
    if not items:
        print("No equipment items found.")
        return
    print(f"\n{'ID':<6}{'Code':<15}{'Name':<25}{'Category':<18}{'Rate':<10}{'Avail':<8}")
    print("-" * 82)
    for item in items:
        print(
            f"{item['item_id']:<6}{item['item_code']:<15}{item['name']:<25}"
            f"{item['category']:<18}£{item['daily_rate']:<9.2f}{item['quantity_available']:<8}"
        )


def _list_available_items():
    """List available equipment items."""
    print("\n--- Available Equipment ---")
    print(f"Categories: {', '.join(EQUIPMENT_CATEGORIES)}")
    category = input("Filter by category (Enter for all): ").strip() or None

    items = EquipmentManager.get_available_items(category)
    if not items:
        print("No available equipment found.")
        return
    print(f"\n{'ID':<6}{'Name':<25}{'Category':<18}{'Rate':<10}{'Avail':<8}")
    print("-" * 67)
    for item in items:
        print(
            f"{item['item_id']:<6}{item['name']:<25}"
            f"{item['category']:<18}£{item['daily_rate']:<9.2f}{item['quantity_available']:<8}"
        )


def _create_rental():
    """Create a new equipment rental."""
    print("\n--- Create Rental ---")
    item_id = int(input("Equipment item ID: ").strip())
    item = EquipmentManager.get_item(item_id)
    if not item:
        print("Item not found.")
        return
    if item['quantity_available'] < 1:
        print("Item not available.")
        return

    print(f"Item: {item['name']} | Rate: £{item['daily_rate']:.2f}/day")

    borrower_id = input("Borrower ID: ").strip()
    borrower_name = input("Borrower name: ").strip()
    borrower_email = input("Borrower email (optional): ").strip() or None
    purpose = input("Purpose (optional): ").strip() or None
    checkout_date = input("Checkout date (YYYY-MM-DD): ").strip()
    checkout_time = input("Checkout time (HH:MM): ").strip()
    due_date = input("Due date (YYYY-MM-DD): ").strip()
    due_time = input("Due time (HH:MM): ").strip()

    rental_id = RentalManager.create_rental(
        item_id, borrower_id, borrower_name,
        checkout_date, checkout_time, due_date, due_time,
        item['daily_rate'],
        borrower_email=borrower_email, purpose=purpose,
    )
    if rental_id:
        print(f"Rental created successfully. Rental ID: {rental_id}")
    else:
        print("Failed to create rental.")


def _view_rental():
    """View rental details."""
    print("\n--- View Rental ---")
    rental_id = int(input("Rental ID: ").strip())
    rental = RentalManager.get_rental(rental_id)
    if not rental:
        print("Rental not found.")
        return
    print(f"\n  Rental ID:     {rental['rental_id']}")
    print(f"  Rental #:      {rental['rental_number']}")
    print(f"  Item:          {rental.get('item_name', 'N/A')} ({rental.get('item_code', '')})")
    print(f"  Borrower:      {rental['borrower_name']} ({rental['borrower_id']})")
    print(f"  Checkout:      {rental['checkout_date']} {rental['checkout_time']}")
    print(f"  Due:           {rental['due_date']} {rental['due_time']}")
    print(f"  Status:        {rental['status']}")
    print(f"  Daily Rate:    £{rental['daily_rate']:.2f}")
    print(f"  Total Days:    {rental['total_days']}")
    print(f"  Total Amount:  £{rental['total_amount']:.2f}")
    print(f"  Payment:       {rental['payment_status']}")
    if rental.get('actual_return_date'):
        print(f"  Returned:      {rental['actual_return_date']} {rental.get('actual_return_time', '')}")


def _checkout_item():
    """Check out equipment (start rental)."""
    print("\n--- Check Out Equipment ---")
    rental_id = int(input("Rental ID: ").strip())
    print(f"Conditions: {', '.join(EQUIPMENT_CONDITIONS)}")
    condition = input("Condition at checkout: ").strip() or None

    if RentalManager.checkout_item(rental_id, condition):
        print("Equipment checked out successfully.")
    else:
        print("Failed to check out equipment.")


def _return_item():
    """Return equipment."""
    print("\n--- Return Equipment ---")
    rental_id = int(input("Rental ID: ").strip())
    print(f"Conditions: {', '.join(EQUIPMENT_CONDITIONS)}")
    condition = input("Condition at return: ").strip()
    late_fee = float(input("Late fee (0 if none): ").strip() or "0")
    damage_fee = float(input("Damage fee (0 if none): ").strip() or "0")

    if RentalManager.return_item(rental_id, condition, late_fee, damage_fee):
        print("Equipment returned successfully.")
    else:
        print("Failed to return equipment.")


def _extend_rental():
    """Extend rental due date."""
    print("\n--- Extend Rental ---")
    rental_id = int(input("Rental ID: ").strip())
    new_due_date = input("New due date (YYYY-MM-DD): ").strip()
    new_due_time = input("New due time (HH:MM): ").strip()

    if RentalManager.extend_rental(rental_id, new_due_date, new_due_time):
        print("Rental extended successfully.")
    else:
        print("Failed to extend rental.")


def _cancel_rental():
    """Cancel a rental."""
    print("\n--- Cancel Rental ---")
    rental_id = int(input("Rental ID: ").strip())
    reason = input("Reason (optional): ").strip() or None

    if RentalManager.cancel_rental(rental_id, reason):
        print("Rental cancelled successfully.")
    else:
        print("Failed to cancel rental.")


def _list_rentals_by_status():
    """List rentals filtered by status."""
    print("\n--- List Rentals ---")
    print(f"Statuses: {', '.join(RENTAL_STATUSES)}")
    status = input("Filter by status (Enter for all): ").strip() or None

    rentals = RentalManager.get_rentals_by_status(status)
    if not rentals:
        print("No rentals found.")
        return
    print(f"\n{'ID':<6}{'Rental #':<20}{'Item':<20}{'Borrower':<18}{'Status':<12}{'Due':<12}")
    print("-" * 88)
    for r in rentals:
        print(
            f"{r['rental_id']:<6}{r['rental_number']:<20}{r.get('item_name', ''):<20}"
            f"{r['borrower_name']:<18}{r['status']:<12}{r['due_date']:<12}"
        )


def _record_payment():
    """Record a payment for a rental."""
    print("\n--- Record Payment ---")
    rental_id = int(input("Rental ID: ").strip())
    borrower_id = input("Borrower ID: ").strip()
    amount = float(input("Amount: ").strip())
    payment_method = input("Payment method (card/cash/transfer): ").strip()

    txn_id = TransactionManager.record_payment(rental_id, borrower_id, amount, payment_method)
    if txn_id:
        print(f"Payment recorded. Transaction ID: {txn_id}")
    else:
        print("Failed to record payment.")


def _refund_deposit():
    """Refund a deposit."""
    print("\n--- Refund Deposit ---")
    rental_id = int(input("Rental ID: ").strip())
    borrower_id = input("Borrower ID: ").strip()
    amount = float(input("Refund amount: ").strip())

    txn_id = TransactionManager.refund_deposit(rental_id, borrower_id, amount)
    if txn_id:
        print(f"Deposit refunded. Transaction ID: {txn_id}")
    else:
        print("Failed to refund deposit.")


def _view_transactions():
    """View transactions."""
    print("\n--- View Transactions ---")
    rental_input = input("Rental ID (Enter for all recent): ").strip()
    rental_id = int(rental_input) if rental_input else None

    transactions = TransactionManager.get_transactions(rental_id)
    if not transactions:
        print("No transactions found.")
        return
    for t in transactions:
        print(
            f"  [{t.get('transaction_id')}] Ref: {t.get('reference_number', 'N/A')} | "
            f"Type: {t.get('transaction_type', 'N/A')} | "
            f"Amount: £{t.get('amount', 0):.2f} | "
            f"Status: {t.get('status', 'N/A')}"
        )


def _inventory_summary():
    """Display inventory summary."""
    print("\n--- Inventory Summary ---")
    summary = ReportManager.get_inventory_summary()
    if not summary:
        print("No data available.")
        return
    print(f"  Total Items:      {summary.get('total_items', 0)}")
    print(f"  Total Quantity:   {summary.get('total_quantity', 0)}")
    print(f"  Available:        {summary.get('available_quantity', 0)}")
    print(f"  Currently Rented: {summary.get('rented_quantity', 0)}")


def _revenue_report():
    """Display revenue report."""
    print("\n--- Revenue Report ---")
    start = input("Start date (YYYY-MM-DD, Enter for all): ").strip() or None
    end = input("End date (YYYY-MM-DD, Enter for all): ").strip() or None

    report = ReportManager.get_revenue_report(start, end)
    if not report:
        print("No data available.")
        return
    print(f"  Total Rentals:     {report.get('total_rentals', 0)}")
    print(f"  Total Revenue:     £{report.get('total_revenue', 0):.2f}")
    print(f"  Avg Rental Value:  £{report.get('avg_rental_value', 0):.2f}")
    print(f"  Late Fees:         £{report.get('total_late_fees', 0):.2f}")
    print(f"  Damage Fees:       £{report.get('total_damage_fees', 0):.2f}")


def _popular_items():
    """Display popular items."""
    print("\n--- Most Popular Items ---")
    limit_str = input("How many (default 10): ").strip()
    limit = int(limit_str) if limit_str else 10

    items = ReportManager.get_popular_items(limit)
    if not items:
        print("No data available.")
        return
    for i, item in enumerate(items, 1):
        print(
            f"  {i}. {item['name']} ({item['category']}) - "
            f"{item.get('rental_count', 0)} rentals, "
            f"£{item.get('total_revenue', 0):.2f} revenue"
        )


def _overdue_rentals():
    """Display overdue rentals."""
    print("\n--- Overdue Rentals ---")
    rentals = ReportManager.get_overdue_rentals()
    if not rentals:
        print("No overdue rentals.")
        return
    for r in rentals:
        print(
            f"  [{r['rental_id']}] {r.get('rental_number', '')} - "
            f"{r.get('item_name', '')} | "
            f"Borrower: {r['borrower_name']} | "
            f"Due: {r['due_date']}"
        )


def _admin_report():
    """Display full admin report."""
    print(ReportManager.generate_admin_report())


if __name__ == "__main__":
    display_menu()
