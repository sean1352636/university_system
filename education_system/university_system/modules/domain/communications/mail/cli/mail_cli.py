"""
Mail/Post System CLI Interface

Command-line interface for mail and package handling services including
receiving, tracking, PO boxes, forwarding, and reporting.
"""

from datetime import datetime

from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import (
    init_mail_db,
    PackageManager,
    POBoxManager,
    ForwardingManager,
    TransactionManager,
    ReportManager,
    PACKAGE_TYPES,
    PACKAGE_STATUSES,
    FORWARDING_FEES,
    STORAGE_FEES,
)


def display_menu():
    """Display the mail/post system menu and handle user input."""
    init_mail_db()

    while True:
        print("\n" + "=" * 70)
        print(" " * 20 + "MAIL / POST SYSTEM MANAGEMENT")
        print("=" * 70)

        print("\n[Packages]")
        print("1.  Receive Package")
        print("2.  View Package")
        print("3.  Search Packages")
        print("4.  Packages for Recipient")
        print("5.  Pending Packages")
        print("6.  Update Package Status")
        print("7.  Mark Package Collected")
        print("8.  Calculate Storage Fees")

        print("\n[PO Boxes]")
        print("9.  Available PO Boxes")
        print("10. Rent PO Box")
        print("11. View User PO Box")
        print("12. Release PO Box")

        print("\n[Forwarding]")
        print("13. Set Up Forwarding")
        print("14. View User Forwarding")
        print("15. Cancel Forwarding")

        print("\n[Payments]")
        print("16. Record Payment")
        print("17. View User Transactions")

        print("\n[Reports]")
        print("18. Daily Report")
        print("19. Monthly Summary")
        print("20. Pending Notifications")

        print("\n0.  Back to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            if choice == "0":
                break
            elif choice == "1":
                _receive_package()
            elif choice == "2":
                _view_package()
            elif choice == "3":
                _search_packages()
            elif choice == "4":
                _packages_for_recipient()
            elif choice == "5":
                _pending_packages()
            elif choice == "6":
                _update_package_status()
            elif choice == "7":
                _mark_collected()
            elif choice == "8":
                _calculate_storage_fees()
            elif choice == "9":
                _available_po_boxes()
            elif choice == "10":
                _rent_po_box()
            elif choice == "11":
                _view_user_po_box()
            elif choice == "12":
                _release_po_box()
            elif choice == "13":
                _setup_forwarding()
            elif choice == "14":
                _view_user_forwarding()
            elif choice == "15":
                _cancel_forwarding()
            elif choice == "16":
                _record_payment()
            elif choice == "17":
                _view_transactions()
            elif choice == "18":
                _daily_report()
            elif choice == "19":
                _monthly_summary()
            elif choice == "20":
                _pending_notifications()
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")


def _receive_package():
    """Receive and register a new package."""
    print("\n--- Receive Package ---")
    recipient_id = input("Recipient ID: ").strip()
    recipient_name = input("Recipient name: ").strip()
    recipient_email = input("Recipient email: ").strip()

    print(f"Package types: {', '.join(PACKAGE_TYPES)}")
    print("Storage fees:")
    for ptype, fee in STORAGE_FEES.items():
        print(f"  {ptype}: ${fee:.2f}")
    package_type = input("Package type: ").strip()
    if package_type not in PACKAGE_TYPES:
        print("Invalid package type.")
        return

    sender_name = input("Sender name (optional): ").strip() or None
    sender_address = input("Sender address (optional): ").strip() or None
    description = input("Description (optional): ").strip() or None
    weight_str = input("Weight in kg (optional): ").strip()
    weight = float(weight_str) if weight_str else None
    storage_location = input("Storage location (optional): ").strip() or None

    result = PackageManager.receive_package(
        recipient_id, recipient_name, recipient_email, package_type,
        sender_name=sender_name, sender_address=sender_address,
        description=description, weight_kg=weight,
        storage_location=storage_location,
    )
    if result:
        print(f"\nPackage received successfully!")
        print(f"  Package ID:       {result['package_id']}")
        print(f"  Tracking Number:  {result['tracking_number']}")
        print(f"  Storage Fee:      ${result['storage_fee']:.2f}")
    else:
        print("Failed to receive package.")


def _view_package():
    """View package details."""
    print("\n--- View Package ---")
    print("Search by: 1) Package ID  2) Tracking Number")
    search_by = input("Choice: ").strip()

    package = None
    if search_by == "1":
        pid = int(input("Package ID: ").strip())
        package = PackageManager.get_package(package_id=pid)
    elif search_by == "2":
        tracking = input("Tracking number: ").strip()
        package = PackageManager.get_package(tracking_number=tracking)
    else:
        print("Invalid choice.")
        return

    if not package:
        print("Package not found.")
        return

    print(f"\n  Package ID:       {package['package_id']}")
    print(f"  Tracking #:       {package['tracking_number']}")
    print(f"  Recipient:        {package['recipient_name']} ({package['recipient_id']})")
    print(f"  Email:            {package.get('recipient_email', 'N/A')}")
    print(f"  Type:             {package['package_type']}")
    print(f"  Sender:           {package.get('sender_name', 'N/A')}")
    print(f"  Status:           {package['status']}")
    print(f"  Storage Location: {package.get('storage_location', 'N/A')}")
    print(f"  Received:         {package.get('received_date', 'N/A')}")
    print(f"  Storage Fee:      ${package.get('storage_fee', 0):.2f}")
    print(f"  Total Charges:    ${package.get('total_charges', 0):.2f}")
    print(f"  Payment Status:   {package.get('payment_status', 'N/A')}")
    if package.get('collected_date'):
        print(f"  Collected:        {package['collected_date']} by {package.get('collected_by', 'N/A')}")
    if package.get('description'):
        print(f"  Description:      {package['description']}")


def _search_packages():
    """Search packages."""
    print("\n--- Search Packages ---")
    search_term = input("Search (tracking #, recipient, sender): ").strip()

    packages = PackageManager.search_packages(search_term)
    if not packages:
        print("No packages found.")
        return

    print(f"\n{'ID':<6}{'Tracking #':<22}{'Recipient':<20}{'Type':<15}{'Status':<12}")
    print("-" * 75)
    for p in packages:
        print(
            f"{p['package_id']:<6}{p['tracking_number']:<22}{p['recipient_name']:<20}"
            f"{p['package_type']:<15}{p['status']:<12}"
        )


def _packages_for_recipient():
    """View packages for a specific recipient."""
    print("\n--- Packages for Recipient ---")
    recipient_id = input("Recipient ID: ").strip()
    print(f"Statuses: {', '.join(PACKAGE_STATUSES)}")
    status = input("Filter by status (Enter for all): ").strip() or None

    packages = PackageManager.get_packages_for_recipient(recipient_id, status)
    if not packages:
        print("No packages found.")
        return

    print(f"\n{'ID':<6}{'Tracking #':<22}{'Type':<15}{'Status':<12}{'Received':<20}")
    print("-" * 75)
    for p in packages:
        print(
            f"{p['package_id']:<6}{p['tracking_number']:<22}{p['package_type']:<15}"
            f"{p['status']:<12}{str(p.get('received_date', 'N/A'))[:10]:<20}"
        )


def _pending_packages():
    """View all pending packages."""
    print("\n--- Pending Packages ---")
    packages = PackageManager.get_pending_packages()
    if not packages:
        print("No pending packages.")
        return

    print(f"\n{'ID':<6}{'Tracking #':<22}{'Recipient':<20}{'Type':<15}{'Status':<12}{'Location':<12}")
    print("-" * 87)
    for p in packages:
        print(
            f"{p['package_id']:<6}{p['tracking_number']:<22}{p['recipient_name']:<20}"
            f"{p['package_type']:<15}{p['status']:<12}{p.get('storage_location', 'N/A'):<12}"
        )


def _update_package_status():
    """Update a package's status."""
    print("\n--- Update Package Status ---")
    package_id = int(input("Package ID: ").strip())
    print(f"Statuses: {', '.join(PACKAGE_STATUSES)}")
    status = input("New status: ").strip()
    notes = input("Notes (optional): ").strip() or None

    if PackageManager.update_package_status(package_id, status, notes):
        print("Package status updated successfully.")
    else:
        print("Failed to update package status.")


def _mark_collected():
    """Mark a package as collected."""
    print("\n--- Mark Package Collected ---")
    package_id = int(input("Package ID: ").strip())
    collected_by = input("Collected by (name/ID): ").strip()

    if PackageManager.mark_collected(package_id, collected_by):
        print("Package marked as collected.")
    else:
        print("Failed to mark package as collected.")


def _calculate_storage_fees():
    """Calculate storage fees for a package."""
    print("\n--- Calculate Storage Fees ---")
    package_id = int(input("Package ID: ").strip())

    fees = PackageManager.calculate_storage_fees(package_id)
    print(f"Current storage fees: ${fees:.2f}")


def _available_po_boxes():
    """List available PO boxes."""
    print("\n--- Available PO Boxes ---")
    boxes = POBoxManager.get_available_boxes()
    if not boxes:
        print("No PO boxes available.")
        return

    print(f"\n{'ID':<6}{'Box #':<12}{'Size':<12}{'Monthly Fee':<14}")
    print("-" * 44)
    for b in boxes:
        print(
            f"{b['box_id']:<6}{b['box_number']:<12}{b['size']:<12}"
            f"${b['monthly_fee']:.2f}"
        )


def _rent_po_box():
    """Rent a PO box."""
    print("\n--- Rent PO Box ---")
    box_id = int(input("Box ID: ").strip())
    holder_id = input("Holder ID: ").strip()
    holder_name = input("Holder name: ").strip()
    holder_email = input("Holder email: ").strip()
    months_str = input("Number of months (default 1): ").strip()
    months = int(months_str) if months_str else 1

    result = POBoxManager.rent_box(box_id, holder_id, holder_name, holder_email, months)
    if result:
        print(f"\nPO box rented successfully!")
        print(f"  Box Number:  {result['box_number']}")
        print(f"  Rental Fee:  ${result['rental_fee']:.2f}")
        print(f"  Start Date:  {result['start_date']}")
        print(f"  End Date:    {result['end_date']}")
    else:
        print("Failed to rent PO box. Box may not be available.")


def _view_user_po_box():
    """View user's PO box."""
    print("\n--- View User PO Box ---")
    user_id = input("User ID: ").strip()

    box = POBoxManager.get_user_box(user_id)
    if not box:
        print("No PO box found for this user.")
        return

    print(f"\n  Box ID:       {box['box_id']}")
    print(f"  Box Number:   {box['box_number']}")
    print(f"  Holder:       {box.get('holder_name', 'N/A')}")
    print(f"  Size:         {box['size']}")
    print(f"  Monthly Fee:  ${box['monthly_fee']:.2f}")
    print(f"  Rental Start: {box.get('rental_start', 'N/A')}")
    print(f"  Rental End:   {box.get('rental_end', 'N/A')}")
    print(f"  Auto-Renew:   {'Yes' if box.get('auto_renew') else 'No'}")


def _release_po_box():
    """Release a PO box rental."""
    print("\n--- Release PO Box ---")
    box_id = int(input("Box ID: ").strip())
    confirm = input("Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if POBoxManager.release_box(box_id):
        print("PO box released successfully.")
    else:
        print("Failed to release PO box.")


def _setup_forwarding():
    """Set up mail forwarding."""
    print("\n--- Set Up Mail Forwarding ---")
    user_id = input("User ID: ").strip()
    user_name = input("User name: ").strip()
    forward_address = input("Forwarding address: ").strip()

    print("Forwarding types and fees:")
    for ftype, fee in FORWARDING_FEES.items():
        print(f"  {ftype}: ${fee:.2f}")
    forward_type = input("Type (domestic/international): ").strip() or "domestic"

    start_date = input("Start date (YYYY-MM-DD, Enter for today): ").strip() or None
    end_date = input("End date (YYYY-MM-DD, optional): ").strip() or None

    result = ForwardingManager.setup_forwarding(
        user_id, user_name, forward_address, forward_type,
        start_date, end_date,
    )
    if result:
        print(f"\nForwarding set up successfully!")
        print(f"  Forwarding ID: {result['forwarding_id']}")
        print(f"  Fee:           ${result['fee']:.2f}")
    else:
        print("Failed to set up forwarding.")


def _view_user_forwarding():
    """View user's forwarding settings."""
    print("\n--- View User Forwarding ---")
    user_id = input("User ID: ").strip()

    forwarding = ForwardingManager.get_user_forwarding(user_id)
    if not forwarding:
        print("No active forwarding found.")
        return

    print(f"\n  Forwarding ID: {forwarding['forwarding_id']}")
    print(f"  User:          {forwarding['user_name']}")
    print(f"  Address:       {forwarding['forward_address']}")
    print(f"  Type:          {forwarding['forward_type']}")
    print(f"  Start Date:    {forwarding['start_date']}")
    print(f"  End Date:      {forwarding.get('end_date', 'N/A')}")
    print(f"  Fee:           ${forwarding.get('fee', 0):.2f}")
    print(f"  Status:        {forwarding['status']}")


def _cancel_forwarding():
    """Cancel mail forwarding."""
    print("\n--- Cancel Forwarding ---")
    forwarding_id = int(input("Forwarding ID: ").strip())
    confirm = input("Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if ForwardingManager.cancel_forwarding(forwarding_id):
        print("Forwarding cancelled successfully.")
    else:
        print("Failed to cancel forwarding.")


def _record_payment():
    """Record a mail service payment."""
    print("\n--- Record Payment ---")
    user_id = input("User ID: ").strip()
    print("Transaction types: storage_fee, po_box_rental, forwarding, collection")
    transaction_type = input("Transaction type: ").strip()
    amount = float(input("Amount: ").strip())
    payment_method = input("Payment method (card/cash/transfer): ").strip()
    pkg_id_str = input("Package ID (optional): ").strip()
    package_id = int(pkg_id_str) if pkg_id_str else None

    result = TransactionManager.record_payment(
        user_id, transaction_type, amount, payment_method, package_id,
    )
    if result:
        print(f"\nPayment recorded!")
        print(f"  Transaction ID: {result['transaction_id']}")
        print(f"  Reference:      {result['reference']}")
        print(f"  Amount:         ${result['amount']:.2f}")
    else:
        print("Failed to record payment.")


def _view_transactions():
    """View user transactions."""
    print("\n--- User Transactions ---")
    user_id = input("User ID: ").strip()

    transactions = TransactionManager.get_user_transactions(user_id)
    if not transactions:
        print("No transactions found.")
        return

    for t in transactions:
        print(
            f"  [{t.get('transaction_id')}] Type: {t.get('transaction_type', 'N/A')} | "
            f"Amount: ${t.get('amount', 0):.2f} | "
            f"Method: {t.get('payment_method', 'N/A')} | "
            f"Ref: {t.get('reference_number', 'N/A')}"
        )


def _daily_report():
    """Display daily operations report."""
    print("\n--- Daily Report ---")
    date = input("Date (YYYY-MM-DD, Enter for today): ").strip() or None

    report = ReportManager.get_daily_report(date)
    if not report:
        print("No data available.")
        return

    print(f"  Date:               {report.get('date', 'N/A')}")
    print(f"  Packages Received:  {report.get('packages_received', 0)}")
    print(f"  Packages Collected: {report.get('packages_collected', 0)}")
    print(f"  Storage Fees:       ${report.get('storage_fees', 0):.2f}")
    print(f"  Total Revenue:      ${report.get('total_revenue', 0):.2f}")


def _monthly_summary():
    """Display monthly summary."""
    print("\n--- Monthly Summary ---")
    year_str = input("Year (Enter for current): ").strip()
    month_str = input("Month (1-12, Enter for current): ").strip()

    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None

    report = ReportManager.get_monthly_summary(year, month)
    if not report:
        print("No data available.")
        return

    print(f"  Period:            {report.get('year', '')}-{report.get('month', ''):02d}")
    print(f"  Total Revenue:     ${report.get('total_revenue', 0):.2f}")
    print(f"  Active PO Boxes:   {report.get('active_po_boxes', 0)}")

    by_type = report.get('packages_by_type', {})
    if by_type:
        print("\n  Packages by Type:")
        for ptype, info in by_type.items():
            print(f"    {ptype}: {info['count']} packages, ${info['revenue']:.2f}")


def _pending_notifications():
    """Display packages pending notification."""
    print("\n--- Pending Notifications ---")
    packages = ReportManager.get_pending_notifications()
    if not packages:
        print("No pending notifications.")
        return

    print(f"\n{'ID':<6}{'Tracking #':<22}{'Recipient':<20}{'Email':<25}{'Received':<12}")
    print("-" * 85)
    for p in packages:
        print(
            f"{p['package_id']:<6}{p['tracking_number']:<22}{p['recipient_name']:<20}"
            f"{p.get('recipient_email', 'N/A'):<25}{str(p.get('received_date', 'N/A'))[:10]:<12}"
        )


if __name__ == "__main__":
    display_menu()
