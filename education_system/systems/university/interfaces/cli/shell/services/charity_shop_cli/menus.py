"""
All CLI menu functions and interactive wrappers.
"""

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports import (
    sqlite3, datetime,
    get_connection, get_text, get_auth, display_language_menu_option,
    TABLE_NAME, CATEGORIES, CONDITIONS,
    ACTIVITY_LOGGER_AVAILABLE, log_read, log_search, log_menu_navigation,
)
import education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports as _imp

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.db import init_charity_shop_db
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.inventory import (
    get_all_stock, search_stock, add_item, update_item,
    mark_as_sold, mark_as_available, delete_item,
    get_stock_summary, get_revenue_summary, get_revenue_by_category, get_stock_by_category,
    bulk_import_items, bulk_export_items,
    adjust_stock_quantity, set_low_stock_alert, view_low_stock_items,
    merge_duplicate_items,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.archive import (
    archive_old_items, restore_archived_items, get_archived_items,
    transfer_between_locations, get_all_locations, add_location,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.pricing import (
    barcode_scanner_integration, set_item_barcode,
    apply_discount, create_sale_bundle, get_bundles,
    price_history_tracker, dynamic_pricing_suggestions,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.promotions import (
    create_promotional_event, get_active_promotions, process_refund,
    layaway_system, get_layaways, gift_card_management, loyalty_points_system,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.reporting import (
    calculate_profit_margin,
    generate_daily_sales_report, generate_weekly_sales_report, generate_monthly_sales_report,
    best_selling_items_report, slow_moving_items_report,
    revenue_trend_analysis, category_performance_comparison, seasonal_trends_report,
    donor_contribution_report, tax_deduction_report,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.customers import (
    register_customer, get_customer, customer_purchase_history,
    customer_wishlist, vip_customer_management, customer_birthday_discounts,
    customer_referral_program, customer_feedback_system,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.donations import (
    record_donation, generate_donation_receipt, donor_database,
    donation_value_estimator, donation_drive_tracker, thank_you_letter_generator,
)
from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli.staff import (
    register_staff, get_all_staff,
    staff_performance_tracker, shift_scheduling,
    task_assignment_system, volunteer_hours_tracker,
    opening_closing_checklist, cash_register_reconciliation,
)


def display_charity_shop_menu() -> None:
    """Display the main menu for the charity shop CLI."""
    auth = _imp.auth

    # Get auth from shared context if not set
    if not auth:
        auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text('charity.not_logged_in', default='\nYou must be logged in to access the Charity Shop.'))
        return

    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE_NAME,))
        if not cursor.fetchone():
            conn.close()
            print("Charity shop database not initialized. Initializing now...")
            if not init_charity_shop_db():
                print("Failed to initialize charity shop database.")
                return
        else:
            conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if not init_charity_shop_db():
            print("Failed to initialize charity shop database.")
            return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_menu_navigation('charity_shop_menu')

    while True:
        print("\n" + "=" * 60)
        print(f"           {get_text('charity.title', default='CHARITY SHOP STOCK MANAGEMENT')}")
        print("=" * 60)

        # Show summary
        stock_summary = get_stock_summary()
        revenue_summary = get_revenue_summary()

        print(f"\n{get_text('charity.summary.stock', default='Stock')}: {stock_summary[0]} {get_text('charity.summary.items', default='items')} | {get_text('charity.summary.qty', default='Qty')}: {stock_summary[1]} | {get_text('charity.summary.value', default='Value')}: \u00a3{stock_summary[2]:.2f}")
        print(f"{get_text('charity.summary.revenue', default='Revenue')}: \u00a3{revenue_summary[2]:.2f} | {get_text('charity.summary.sold', default='Sold')}: {revenue_summary[1]} {get_text('charity.summary.items', default='items')}")
        print("-" * 60)

        # Build menu based on permissions
        options = []
        option_num = 1

        # View options (available to all)
        print(f"\n{option_num}. {get_text('charity.menu.view_all', default='View All Stock')}")
        options.append('view_all')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.view_available', default='View Available Stock')}")
        options.append('view_available')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.view_sold', default='View Sold Items')}")
        options.append('view_sold')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.search', default='Search Stock')}")
        options.append('search')
        option_num += 1

        # Management options (staff/admin)
        if auth.check_permission('add_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.add', default='Add New Item')}")
            options.append('add')
            option_num += 1

        if auth.check_permission('edit_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.edit', default='Edit Item')}")
            options.append('edit')
            option_num += 1

        if auth.check_permission('sell_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.sell', default='Sell Item')}")
            options.append('sell')
            option_num += 1

            print(f"{option_num}. {get_text('charity.menu.mark_available', default='Mark Item Available')}")
            options.append('mark_available')
            option_num += 1

        if auth.check_permission('delete_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.delete', default='Delete Item')}")
            options.append('delete')
            option_num += 1

        # Reports (staff/admin)
        if auth.check_permission('view_charity_shop_reports') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.reports', default='View Reports')}")
            options.append('reports')
            option_num += 1

        # Advanced management submenus (staff/admin)
        if auth.check_permission('manage_charity_shop') or auth.check_permission('edit_charity_shop_item'):
            print("\n--- Advanced Management ---")
            print(f"{option_num}. Inventory Management")
            options.append('inventory')
            option_num += 1

            print(f"{option_num}. Sales & Pricing")
            options.append('sales_pricing')
            option_num += 1

            print(f"{option_num}. Customer Management")
            options.append('customers')
            option_num += 1

            print(f"{option_num}. Donation Management")
            options.append('donations')
            option_num += 1

            print(f"{option_num}. Staff & Operations")
            options.append('staff_ops')
            option_num += 1

        # Language option
        print(f"\n{option_num}. {get_text('charity.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.return', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('charity.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_num = int(choice)

            if choice_num > 0 and choice_num <= len(options):
                selected = options[choice_num - 1]

                if selected == 'view_all':
                    view_stock_cli('all')
                elif selected == 'view_available':
                    view_stock_cli('available')
                elif selected == 'view_sold':
                    view_stock_cli('sold')
                elif selected == 'search':
                    search_stock_cli()
                elif selected == 'add':
                    add_item_cli()
                elif selected == 'edit':
                    edit_item_cli()
                elif selected == 'sell':
                    sell_item_cli()
                elif selected == 'mark_available':
                    mark_available_cli()
                elif selected == 'delete':
                    delete_item_cli()
                elif selected == 'reports':
                    view_reports_cli()
                elif selected == 'inventory':
                    inventory_management_cli()
                elif selected == 'sales_pricing':
                    sales_pricing_cli()
                elif selected == 'customers':
                    customer_management_cli()
                elif selected == 'donations':
                    donation_management_cli()
                elif selected == 'staff_ops':
                    staff_operations_cli()
                elif selected == 'language':
                    display_language_menu_option()

            elif choice_num == len(options) + 1:
                print(get_text('charity.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('charity.invalid_choice', default='Invalid choice. Please try again.'))

        except ValueError:
            if choice.lower() in ['q', 'quit', 'exit', 'back']:
                break
            print(get_text('charity.invalid_input', default='Invalid input. Please enter a number.'))


def view_stock_cli(filter_type: str = 'all') -> None:
    """View stock items in CLI."""
    stock = get_all_stock(filter_type)

    if not stock:
        print(f"\nNo {'sold ' if filter_type == 'sold' else 'available ' if filter_type == 'available' else ''}items found.")
        return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_read('charity_shop_stock', filter=filter_type, count=len(stock))

    print(f"\n{'=' * 100}")
    print(f"{'ID':<5} {'Name':<25} {'Category':<12} {'Price':<10} {'Qty':<5} {'Condition':<10} {'Status':<10} {'Sold':<5}")
    print(f"{'=' * 100}")

    for item in stock:
        item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item
        status = "Sold" if sold else "Available"
        print(f"{item_id:<5} {name[:24]:<25} {category:<12} \u00a3{price:<9.2f} {qty:<5} {condition:<10} {status:<10} {sold_qty or 0:<5}")

    print(f"{'=' * 100}")
    print(f"Total: {len(stock)} items")

    input("\nPress Enter to continue...")


def search_stock_cli() -> None:
    """Search stock items."""
    print("\n--- Search Stock ---")
    search_term = input("Enter search term (item name): ").strip()

    print("\nCategories: All, " + ", ".join(CATEGORIES))
    category = input("Filter by category (or 'All'): ").strip()
    if category not in ["All"] + CATEGORIES:
        category = "All"

    print("\nStatus: all, available, sold")
    status = input("Filter by status: ").strip().lower()
    if status not in ['all', 'available', 'sold']:
        status = 'all'

    results = search_stock(search_term, category, status)

    if ACTIVITY_LOGGER_AVAILABLE:
        log_search('charity_shop_stock', search_term=search_term, results_count=len(results))

    if not results:
        print("\nNo items found matching your criteria.")
    else:
        print(f"\n{'=' * 100}")
        print(f"{'ID':<5} {'Name':<25} {'Category':<12} {'Price':<10} {'Qty':<5} {'Condition':<10} {'Status':<10}")
        print(f"{'=' * 100}")

        for item in results:
            item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item
            status = "Sold" if sold else "Available"
            print(f"{item_id:<5} {name[:24]:<25} {category:<12} \u00a3{price:<9.2f} {qty:<5} {condition:<10} {status:<10}")

        print(f"\nFound {len(results)} items.")

    input("\nPress Enter to continue...")


def add_item_cli() -> None:
    """Add a new item via CLI."""
    print("\n--- Add New Item ---")

    name = input("Item name: ").strip()
    if not name:
        print("Item name is required.")
        return

    print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
    try:
        cat_choice = int(input("Select category (number): "))
        if 1 <= cat_choice <= len(CATEGORIES):
            category = CATEGORIES[cat_choice - 1]
        else:
            category = "Other"
    except ValueError:
        category = "Other"

    try:
        price = float(input("Price (\u00a3): "))
        if price < 0:
            print("Price must be positive.")
            return
    except ValueError:
        print("Invalid price.")
        return

    try:
        quantity = int(input("Quantity: "))
        if quantity < 0:
            print("Quantity must be positive.")
            return
    except ValueError:
        print("Invalid quantity.")
        return

    print("\nConditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
    try:
        cond_choice = int(input("Select condition (number): "))
        if 1 <= cond_choice <= len(CONDITIONS):
            condition = CONDITIONS[cond_choice - 1]
        else:
            condition = "Good"
    except ValueError:
        condition = "Good"

    if add_item(name, category, price, quantity, condition):
        print(f"\n\u2705 Item '{name}' added successfully!")
    else:
        print("\n\u274c Failed to add item.")

    input("\nPress Enter to continue...")


def edit_item_cli() -> None:
    """Edit an existing item via CLI."""
    print("\n--- Edit Item ---")

    try:
        item_id = int(input("Enter item ID to edit: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get current item
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item

    print("\nCurrent values:")
    print(f"  Name: {name}")
    print(f"  Category: {category}")
    print(f"  Price: \u00a3{price:.2f}")
    print(f"  Quantity: {qty}")
    print(f"  Condition: {condition}")

    print("\n(Press Enter to keep current value)")

    new_name = input(f"New name [{name}]: ").strip() or name

    print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
    cat_input = input(f"New category [{category}]: ").strip()
    try:
        cat_choice = int(cat_input)
        if 1 <= cat_choice <= len(CATEGORIES):
            new_category = CATEGORIES[cat_choice - 1]
        else:
            new_category = category
    except ValueError:
        new_category = category

    price_input = input(f"New price [{price:.2f}]: ").strip()
    try:
        new_price = float(price_input) if price_input else price
    except ValueError:
        new_price = price

    qty_input = input(f"New quantity [{qty}]: ").strip()
    try:
        new_qty = int(qty_input) if qty_input else qty
    except ValueError:
        new_qty = qty

    print("\nConditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
    cond_input = input(f"New condition [{condition}]: ").strip()
    try:
        cond_choice = int(cond_input)
        if 1 <= cond_choice <= len(CONDITIONS):
            new_condition = CONDITIONS[cond_choice - 1]
        else:
            new_condition = condition
    except ValueError:
        new_condition = condition

    if update_item(item_id, new_name, new_category, new_price, new_qty, new_condition, bool(sold), sold_qty or 0):
        print("\n\u2705 Item updated successfully!")
    else:
        print("\n\u274c Failed to update item.")

    input("\nPress Enter to continue...")


def sell_item_cli() -> None:
    """Sell an item via CLI."""
    print("\n--- Sell Item ---")

    try:
        item_id = int(input("Enter item ID to sell: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get current item
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT name, quantity, price FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    name, available_qty, price = item

    if available_qty <= 0:
        print(f"'{name}' is out of stock.")
        return

    print(f"\nItem: {name}")
    print(f"Available: {available_qty}")
    print(f"Price: \u00a3{price:.2f}")

    try:
        qty_to_sell = int(input(f"Quantity to sell (1-{available_qty}): "))
        if qty_to_sell < 1 or qty_to_sell > available_qty:
            print("Invalid quantity.")
            return
    except ValueError:
        print("Invalid quantity.")
        return

    revenue = qty_to_sell * price

    confirm = input(f"\nSell {qty_to_sell} x '{name}' for \u00a3{revenue:.2f}? (y/n): ").strip().lower()
    if confirm == 'y':
        if mark_as_sold(item_id, qty_to_sell):
            print(f"\n\u2705 Sold {qty_to_sell} x '{name}' for \u00a3{revenue:.2f}!")
        else:
            print("\n\u274c Failed to process sale.")
    else:
        print("Sale cancelled.")

    input("\nPress Enter to continue...")


def mark_available_cli() -> None:
    """Mark an item as available via CLI."""
    print("\n--- Mark Item Available ---")

    try:
        item_id = int(input("Enter item ID: "))
    except ValueError:
        print("Invalid ID.")
        return

    if mark_as_available(item_id):
        print("\n\u2705 Item marked as available!")
    else:
        print("\n\u274c Failed to update item.")

    input("\nPress Enter to continue...")


def delete_item_cli() -> None:
    """Delete an item via CLI."""
    print("\n--- Delete Item ---")

    try:
        item_id = int(input("Enter item ID to delete: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get item name
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    confirm = input(f"Are you sure you want to delete '{item[0]}'? (y/n): ").strip().lower()
    if confirm == 'y':
        if delete_item(item_id):
            print(f"\n\u2705 Item '{item[0]}' deleted!")
        else:
            print("\n\u274c Failed to delete item.")
    else:
        print("Deletion cancelled.")

    input("\nPress Enter to continue...")


def view_reports_cli() -> None:
    """View charity shop reports."""
    while True:
        print("\n--- Charity Shop Reports ---")
        print("1. Stock Summary")
        print("2. Revenue Summary")
        print("3. Revenue by Category")
        print("4. Stock by Category")
        print("5. Daily Sales Report")
        print("6. Weekly Sales Report")
        print("7. Monthly Sales Report")
        print("8. Best Selling Items")
        print("9. Slow Moving Items")
        print("10. Category Performance")
        print("11. Seasonal Trends")
        print("12. Profit Margins")
        print("13. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            summary = get_stock_summary()
            print(f"\n{'=' * 40}")
            print("STOCK SUMMARY")
            print(f"{'=' * 40}")
            print(f"Total unique items: {summary[0]}")
            print(f"Total quantity: {summary[1]}")
            print(f"Total stock value: \u00a3{summary[2]:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            summary = get_revenue_summary()
            print(f"\n{'=' * 40}")
            print("REVENUE SUMMARY")
            print(f"{'=' * 40}")
            print(f"Items with sales: {summary[0]}")
            print(f"Total items sold: {summary[1]}")
            print(f"Total revenue: \u00a3{summary[2]:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            revenue = get_revenue_by_category()
            print(f"\n{'=' * 40}")
            print("REVENUE BY CATEGORY")
            print(f"{'=' * 40}")
            if revenue:
                for cat, rev in revenue:
                    print(f"{cat:<20} \u00a3{rev:.2f}")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            stock = get_stock_by_category()
            print(f"\n{'=' * 40}")
            print("STOCK BY CATEGORY")
            print(f"{'=' * 40}")
            if stock:
                for cat, count, qty in stock:
                    print(f"{cat:<20} {count} items ({qty} units)")
            else:
                print("No stock data available.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            date = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip() or None
            report = generate_daily_sales_report(date)
            print(f"\n{'=' * 50}")
            print(f"DAILY SALES REPORT - {report['date']}")
            print(f"{'=' * 50}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: \u00a3{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            if report['by_payment_method']:
                print("\nBy Payment Method:")
                for pm in report['by_payment_method']:
                    print(f"  {pm['method']}: {pm['count']} transactions, \u00a3{pm['amount']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            report = generate_weekly_sales_report()
            print(f"\n{'=' * 50}")
            print("WEEKLY SALES REPORT")
            print(f"{'=' * 50}")
            print(f"Period: {report['start_date']} to {report['end_date']}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: \u00a3{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            if report['daily_breakdown']:
                print("\nDaily Breakdown:")
                for day in report['daily_breakdown']:
                    print(f"  {day['date']}: {day['transactions']} trans, \u00a3{day['revenue']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            report = generate_monthly_sales_report()
            print(f"\n{'=' * 50}")
            print(f"MONTHLY SALES REPORT - {report['year']}/{report['month']:02d}")
            print(f"{'=' * 50}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: \u00a3{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            print(f"Average Transaction: \u00a3{report['average_transaction']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '8':
            items = best_selling_items_report()
            print(f"\n{'=' * 60}")
            print("BEST SELLING ITEMS (Last 30 Days)")
            print(f"{'=' * 60}")
            if items:
                for i, item in enumerate(items, 1):
                    print(f"{i}. {item['name']} ({item['category']})")
                    print(f"   Sold: {item['quantity_sold']} | Revenue: \u00a3{item['revenue']:.2f}")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            items = slow_moving_items_report()
            print(f"\n{'=' * 60}")
            print("SLOW MOVING ITEMS (60+ Days)")
            print(f"{'=' * 60}")
            if items:
                for item in items:
                    print(f"ID {item['id']}: {item['name']} - \u00a3{item['price']:.2f}")
                    print(f"   {item['days_in_stock']} days in stock | Qty: {item['quantity']}")
            else:
                print("No slow-moving items found.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            results = category_performance_comparison()
            print(f"\n{'=' * 70}")
            print("CATEGORY PERFORMANCE (Last 30 Days)")
            print(f"{'=' * 70}")
            print(f"{'Category':<15} {'Trans':<8} {'Items':<8} {'Revenue':<12} {'Avg Sale':<10}")
            print("-" * 70)
            for r in results:
                print(f"{r['category']:<15} {r['transactions']:<8} {r['items_sold']:<8} \u00a3{r['revenue']:<11.2f} \u00a3{r['average_sale']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '11':
            trends = seasonal_trends_report()
            print(f"\n{'=' * 50}")
            print("SEASONAL TRENDS")
            print(f"{'=' * 50}")
            print("\nBy Month:")
            for month, data in trends['by_month'].items():
                print(f"  {month}: {data['transactions']} trans, \u00a3{data['revenue']:.2f}")
            print("\nBy Day of Week:")
            for day, data in trends['by_day_of_week'].items():
                print(f"  {day}: {data['transactions']} trans, \u00a3{data['revenue']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '12':
            margins = calculate_profit_margin()
            print(f"\n{'=' * 50}")
            print("PROFIT MARGINS")
            print(f"{'=' * 50}")
            print(f"Total Revenue: \u00a3{margins['total_revenue']:.2f}")
            print(f"Total Profit: \u00a3{margins['total_profit']:.2f}")
            print(f"Margin: {margins['margin_percent']:.1f}%")
            input("\nPress Enter to continue...")

        elif choice == '13':
            break


def inventory_management_cli() -> None:
    """Inventory management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       INVENTORY MANAGEMENT")
        print("=" * 50)
        print("1. Bulk Import Items (CSV)")
        print("2. Bulk Export Items (CSV)")
        print("3. Adjust Stock Quantity")
        print("4. Set Low Stock Alert")
        print("5. View Low Stock Items")
        print("6. Merge Duplicate Items")
        print("7. Archive Old Items")
        print("8. View/Restore Archived Items")
        print("9. Transfer Between Locations")
        print("10. Barcode Lookup")
        print("11. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            file_path = input("Enter CSV file path: ").strip()
            if file_path:
                success, errors = bulk_import_items(file_path)
                if errors == -1:
                    print("\n\u274c File not found.")
                else:
                    print(f"\n\u2705 Imported {success} items, {errors} errors.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            file_path = input("Enter export file path (e.g., inventory.csv): ").strip()
            if file_path:
                filter_type = input("Filter (all/available/sold) [all]: ").strip() or "all"
                if bulk_export_items(file_path, filter_type):
                    print(f"\n\u2705 Exported to {file_path}")
                else:
                    print("\n\u274c Export failed.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                item_id = int(input("Item ID: "))
                adjustment = int(input("Adjustment (+/-): "))
                reason = input("Reason (optional): ").strip()
                if adjust_stock_quantity(item_id, adjustment, reason):
                    print("\n\u2705 Stock adjusted!")
                else:
                    print("\n\u274c Failed to adjust stock.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                item_id = int(input("Item ID: "))
                threshold = int(input("Low stock threshold: "))
                if set_low_stock_alert(item_id, threshold):
                    print("\n\u2705 Alert threshold set!")
                else:
                    print("\n\u274c Failed to set alert.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = view_low_stock_items()
            print(f"\n{'=' * 60}")
            print("LOW STOCK ITEMS")
            print(f"{'=' * 60}")
            if items:
                for item in items:
                    print(f"ID {item[0]}: {item[1]} ({item[2]}) - Qty: {item[3]}, Threshold: {item[4]}")
            else:
                print("No low stock items.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            try:
                keep_id = int(input("Item ID to keep: "))
                merge_id = int(input("Item ID to merge (will be deleted): "))
                if merge_duplicate_items(keep_id, merge_id):
                    print("\n\u2705 Items merged!")
                else:
                    print("\n\u274c Failed to merge.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                days = int(input("Archive items older than (days) [90]: ") or "90")
                count = archive_old_items(days)
                print(f"\n\u2705 Archived {count} items.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            archived = get_archived_items()
            print(f"\n{'=' * 60}")
            print("ARCHIVED ITEMS")
            print(f"{'=' * 60}")
            if archived:
                for item in archived:
                    print(f"ID {item[0]}: {item[2]} - Archived: {item[7]}")
                restore = input("\nEnter IDs to restore (comma-separated) or press Enter: ").strip()
                if restore:
                    ids = [int(x.strip()) for x in restore.split(",")]
                    count = restore_archived_items(ids)
                    print(f"\n\u2705 Restored {count} items.")
            else:
                print("No archived items.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            locations = get_all_locations()
            if not locations:
                print("\nNo locations configured. Add locations first.")
            else:
                print("\nLocations:")
                for loc in locations:
                    print(f"  {loc['id']}: {loc['name']}")
                try:
                    item_id = int(input("Item ID: "))
                    from_loc = int(input("From location ID: "))
                    to_loc = int(input("To location ID: "))
                    qty = int(input("Quantity: "))
                    if transfer_between_locations(item_id, from_loc, to_loc, qty):
                        print("\n\u2705 Transfer complete!")
                    else:
                        print("\n\u274c Transfer failed.")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            barcode = input("Enter barcode: ").strip()
            item = barcode_scanner_integration(barcode)
            if item:
                print(f"\nFound: {item['name']} (ID: {item['id']})")
                print(f"Price: \u00a3{item['price']:.2f} | Qty: {item['quantity']}")
            else:
                print("\nNo item found with that barcode.")
                assign = input("Assign to item ID? ").strip()
                if assign:
                    try:
                        if set_item_barcode(int(assign), barcode):
                            print("\u2705 Barcode assigned!")
                    except ValueError:
                        pass
            input("\nPress Enter to continue...")

        elif choice == '11':
            break


def sales_pricing_cli() -> None:
    """Sales and pricing submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       SALES & PRICING")
        print("=" * 50)
        print("1. Apply Discount to Item")
        print("2. Create Sale Bundle")
        print("3. View Bundles")
        print("4. Price History")
        print("5. Dynamic Pricing Suggestions")
        print("6. Create Promotional Event")
        print("7. View Active Promotions")
        print("8. Process Refund")
        print("9. Layaway Management")
        print("10. Gift Card Management")
        print("11. Loyalty Points")
        print("12. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            try:
                item_id = int(input("Item ID: "))
                print("Discount type: 1. Percentage  2. Fixed amount")
                dtype = input("Choice: ").strip()
                discount_type = 'percent' if dtype == '1' else 'fixed'
                value = float(input(f"{'Percentage' if dtype == '1' else 'Amount'}: "))
                if apply_discount(item_id, discount_type, value):
                    print("\n\u2705 Discount applied!")
                else:
                    print("\n\u274c Failed to apply discount.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            name = input("Bundle name: ").strip()
            description = input("Description: ").strip()
            item_ids_str = input("Item IDs (comma-separated): ").strip()
            try:
                item_ids = [int(x.strip()) for x in item_ids_str.split(",")]
                bundle_price = float(input("Bundle price: \u00a3"))
                bundle_id = create_sale_bundle(name, description, item_ids, bundle_price)
                if bundle_id:
                    print(f"\n\u2705 Bundle created (ID: {bundle_id})")
                else:
                    print("\n\u274c Failed to create bundle.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            bundles = get_bundles()
            print(f"\n{'=' * 60}")
            print("ACTIVE BUNDLES")
            print(f"{'=' * 60}")
            for b in bundles:
                print(f"ID {b['id']}: {b['name']} - \u00a3{b['bundle_price']:.2f}")
                print(f"   Items: {b['item_ids']} | Sold: {b['times_sold']} times")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                item_id = int(input("Item ID: "))
                history = price_history_tracker(item_id)
                print(f"\n{'=' * 60}")
                print("PRICE HISTORY")
                print(f"{'=' * 60}")
                for h in history:
                    print(f"{h['change_date']}: \u00a3{h['old_price']:.2f} \u2192 \u00a3{h['new_price']:.2f}")
                    if h['reason']:
                        print(f"   Reason: {h['reason']}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                item_id = int(input("Item ID: "))
                suggestion = dynamic_pricing_suggestions(item_id)
                if suggestion:
                    print(f"\nCurrent Price: \u00a3{suggestion['current_price']:.2f}")
                    print(f"Suggested Price: \u00a3{suggestion['suggested_price']:.2f}")
                    print(f"Category Average: \u00a3{suggestion['category_average']:.2f}")
                    print(f"Days in Stock: {suggestion['days_in_stock']}")
                    print(f"Condition: {suggestion['condition']}")
                    print(f"\n{suggestion['reason']}")
                else:
                    print("Item not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            name = input("Promotion name: ").strip()
            print("Discount type: 1. Percentage  2. Fixed amount")
            dtype = input("Choice: ").strip()
            discount_type = 'percent' if dtype == '1' else 'fixed'
            try:
                value = float(input("Discount value: "))
                start = input("Start date (YYYY-MM-DD): ").strip()
                end = input("End date (YYYY-MM-DD): ").strip()
                category = input("Category (optional): ").strip() or None
                promo_id = create_promotional_event(name, discount_type, value, start, end, category)
                if promo_id:
                    print(f"\n\u2705 Promotion created (ID: {promo_id})")
                else:
                    print("\n\u274c Failed to create promotion.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            promos = get_active_promotions()
            print(f"\n{'=' * 60}")
            print("ACTIVE PROMOTIONS")
            print(f"{'=' * 60}")
            if promos:
                for p in promos:
                    pound = '\u00a3'
                    suffix = '%' if p['discount_type'] == 'percent' else pound
                    print(f"{p['name']}: {p['discount_value']}{suffix} off")
                    print(f"   {p['start_date']} to {p['end_date']}")
                    if p['category']:
                        print(f"   Category: {p['category']}")
            else:
                print("No active promotions.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            try:
                sale_id = int(input("Sale ID to refund: "))
                reason = input("Refund reason: ").strip()
                if process_refund(sale_id, reason):
                    print("\n\u2705 Refund processed!")
                else:
                    print("\n\u274c Failed to process refund.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            layaway_menu_cli()

        elif choice == '10':
            gift_card_menu_cli()

        elif choice == '11':
            loyalty_menu_cli()

        elif choice == '12':
            break


def layaway_menu_cli() -> None:
    """Layaway submenu."""
    while True:
        print("\n--- Layaway Management ---")
        print("1. Create Layaway")
        print("2. View Active Layaways")
        print("3. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                item_id = int(input("Item ID: "))
                customer_id = int(input("Customer ID: "))
                deposit = float(input("Deposit amount: \u00a3"))
                days = int(input("Due in (days) [30]: ") or "30")
                layaway_id = layaway_system(item_id, customer_id, deposit, days)
                if layaway_id:
                    print(f"\n\u2705 Layaway created (ID: {layaway_id})")
                else:
                    print("\n\u274c Failed to create layaway.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            layaways = get_layaways()
            print(f"\n{'=' * 70}")
            print("ACTIVE LAYAWAYS")
            print(f"{'=' * 70}")
            for l in layaways:
                print(f"ID {l['id']}: {l['item_name']} for {l['customer_name']}")
                print(f"   Total: \u00a3{l['total_price']:.2f} | Paid: \u00a3{l['deposit_paid']:.2f} | Due: {l['due_date']}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            break


def gift_card_menu_cli() -> None:
    """Gift card submenu."""
    while True:
        print("\n--- Gift Card Management ---")
        print("1. Issue Gift Card")
        print("2. Check Balance")
        print("3. Redeem Gift Card")
        print("4. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                amount = float(input("Gift card amount: \u00a3"))
                customer_id = input("Customer ID (optional): ").strip()
                cid = int(customer_id) if customer_id else None
                result = gift_card_management('issue', amount=amount, customer_id=cid)
                if result:
                    print("\n\u2705 Gift Card Issued!")
                    print(f"Code: {result['code']}")
                    print(f"Balance: \u00a3{result['balance']:.2f}")
                    print(f"Expires: {result['expiry']}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            code = input("Gift card code: ").strip()
            result = gift_card_management('check_balance', code=code)
            if result:
                print(f"\nBalance: \u00a3{result['balance']:.2f}")
                print(f"Expires: {result['expiry']}")
                print(f"Active: {'Yes' if result['active'] else 'No'}")
            else:
                print("Gift card not found.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                code = input("Gift card code: ").strip()
                amount = float(input("Amount to redeem: \u00a3"))
                result = gift_card_management('redeem', code=code, amount=amount)
                if result:
                    print(f"\n\u2705 Redeemed \u00a3{result['redeemed']:.2f}")
                    print(f"New balance: \u00a3{result['new_balance']:.2f}")
                else:
                    print("\n\u274c Redemption failed (invalid card or insufficient balance).")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            break


def loyalty_menu_cli() -> None:
    """Loyalty points submenu."""
    while True:
        print("\n--- Loyalty Points ---")
        print("1. Check Points")
        print("2. Add Points")
        print("3. Redeem Points")
        print("4. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                customer_id = int(input("Customer ID: "))
                points = loyalty_points_system(customer_id, 'check')
                print(f"\nLoyalty Points: {points}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                customer_id = int(input("Customer ID: "))
                points = int(input("Points to add: "))
                reason = input("Reason: ").strip()
                if loyalty_points_system(customer_id, 'add', points=points, reason=reason):
                    print("\n\u2705 Points added!")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                customer_id = int(input("Customer ID: "))
                points = int(input("Points to redeem: "))
                if loyalty_points_system(customer_id, 'redeem', points=points):
                    print("\n\u2705 Points redeemed!")
                else:
                    print("\n\u274c Insufficient points.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            break


def customer_management_cli() -> None:
    """Customer management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       CUSTOMER MANAGEMENT")
        print("=" * 50)
        print("1. Register Customer")
        print("2. View Customer")
        print("3. Customer Purchase History")
        print("4. Customer Wishlist")
        print("5. VIP Management")
        print("6. Birthday Discounts")
        print("7. Referral Program")
        print("8. Customer Feedback")
        print("9. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Customer name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            birthday = input("Birthday YYYY-MM-DD (optional): ").strip() or None
            customer_id = register_customer(name, email, phone, address, birthday)
            if customer_id:
                print(f"\n\u2705 Customer registered (ID: {customer_id})")
            else:
                print("\n\u274c Registration failed.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                customer_id = int(input("Customer ID: "))
                customer = get_customer(customer_id)
                if customer:
                    print(f"\n{'=' * 40}")
                    print(f"Name: {customer['name']}")
                    print(f"Email: {customer['email']}")
                    print(f"Phone: {customer['phone']}")
                    print(f"VIP: {'Yes' if customer['is_vip'] else 'No'}")
                    print(f"Loyalty Points: {customer['loyalty_points']}")
                    print(f"Total Spent: \u00a3{customer['total_spent']:.2f}")
                    print(f"Referral Code: {customer['referral_code']}")
                else:
                    print("Customer not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                customer_id = int(input("Customer ID: "))
                history = customer_purchase_history(customer_id)
                print(f"\n{'=' * 60}")
                print("PURCHASE HISTORY")
                print(f"{'=' * 60}")
                for h in history:
                    status = " (REFUNDED)" if h['refunded'] else ""
                    print(f"{h['date']}: {h['item_name']} x{h['quantity']} - \u00a3{h['amount']:.2f}{status}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                customer_id = int(input("Customer ID: "))
                print("1. View Wishlist  2. Add Item  3. Remove Item")
                action = input("Choice: ").strip()
                if action == '1':
                    items = customer_wishlist(customer_id, 'view')
                    print("\nWishlist:")
                    for item in items:
                        print(f"  {item['id']}: {item['description']} (Max: \u00a3{item['max_price']})")
                elif action == '2':
                    desc = input("Item description: ").strip()
                    cat = input("Category (optional): ").strip() or None
                    price = input("Max price (optional): ").strip()
                    max_price = float(price) if price else None
                    customer_wishlist(customer_id, 'add', description=desc, category=cat, max_price=max_price)
                    print("\u2705 Added to wishlist!")
                elif action == '3':
                    wid = int(input("Wishlist item ID: "))
                    customer_wishlist(customer_id, 'remove', wishlist_id=wid)
                    print("\u2705 Removed!")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            print("1. List VIPs  2. Make VIP  3. Remove VIP  4. Auto-Promote")
            action = input("Choice: ").strip()
            if action == '1':
                vips = vip_customer_management('list_vips')
                print("\nVIP Customers:")
                for v in vips:
                    print(f"  {v['name']} - Spent: \u00a3{v['total_spent']:.2f}, Points: {v['loyalty_points']}")
            elif action == '2':
                try:
                    cid = int(input("Customer ID: "))
                    vip_customer_management('make_vip', cid)
                    print("\u2705 Customer is now VIP!")
                except ValueError:
                    print("Invalid input.")
            elif action == '3':
                try:
                    cid = int(input("Customer ID: "))
                    vip_customer_management('remove_vip', cid)
                    print("\u2705 VIP status removed!")
                except ValueError:
                    print("Invalid input.")
            elif action == '4':
                count = vip_customer_management('auto_promote')
                print(f"\u2705 Promoted {count} customers to VIP!")
            input("\nPress Enter to continue...")

        elif choice == '6':
            customers = customer_birthday_discounts()
            print("\nCustomers with birthdays this month:")
            for c in customers:
                print(f"  {c['name']} - {c['birthday']} ({c['email']})")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                code = input("Referrer's code: ").strip()
                new_id = int(input("New customer ID: "))
                if customer_referral_program(code, new_id):
                    print("\u2705 Referral processed! Points awarded.")
                else:
                    print("\u274c Invalid referral code.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            print("1. Submit Feedback  2. View Item Feedback")
            action = input("Choice: ").strip()
            if action == '1':
                try:
                    cid = int(input("Customer ID: "))
                    iid = int(input("Item ID: "))
                    rating = int(input("Rating (1-5): "))
                    comment = input("Comment: ").strip()
                    customer_feedback_system('submit', customer_id=cid, item_id=iid, rating=rating, comment=comment)
                    print("\u2705 Feedback submitted!")
                except ValueError:
                    print("Invalid input.")
            elif action == '2':
                try:
                    iid = int(input("Item ID: "))
                    feedback = customer_feedback_system('view_item', item_id=iid)
                    avg = customer_feedback_system('average', item_id=iid)
                    print(f"\nAverage Rating: {avg['average']:.1f}/5 ({avg['count']} reviews)")
                    for f in feedback:
                        print(f"  {f['rating']}/5 - {f['comment']} ({f['customer_name']})")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            break


def donation_management_cli() -> None:
    """Donation management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       DONATION MANAGEMENT")
        print("=" * 50)
        print("1. Register Donor")
        print("2. Record Donation")
        print("3. Generate Donation Receipt")
        print("4. View Donors")
        print("5. Donation Value Estimator")
        print("6. Donation Drive Summary")
        print("7. Thank You Letter")
        print("8. Tax Deduction Report")
        print("9. Donor Contribution Report")
        print("10. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Donor name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            donor_id = donor_database('add', name=name, email=email, phone=phone, address=address)
            if donor_id:
                print(f"\n\u2705 Donor registered (ID: {donor_id})")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                donor_id = int(input("Donor ID: "))
                description = input("Item description: ").strip()
                print("Categories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
                cat_num = input("Category number: ").strip()
                category = CATEGORIES[int(cat_num)-1] if cat_num else None
                qty = int(input("Quantity [1]: ") or "1")
                print("Conditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
                cond_num = input("Condition number: ").strip()
                condition = CONDITIONS[int(cond_num)-1] if cond_num else "Good"
                est_value = donation_value_estimator(category or "Other", condition)
                print(f"Estimated value: \u00a3{est_value:.2f}")
                use_est = input("Use this value? (y/n) [y]: ").strip().lower() != 'n'
                value = est_value if use_est else float(input("Enter value: \u00a3"))
                drive_id = input("Donation drive ID (optional): ").strip() or None
                notes = input("Notes (optional): ").strip() or None
                donation_id = record_donation(donor_id, description, category, qty, value, drive_id, notes)
                if donation_id:
                    print(f"\n\u2705 Donation recorded (ID: {donation_id})")
            except (ValueError, IndexError):
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                donation_id = int(input("Donation ID: "))
                receipt = generate_donation_receipt(donation_id)
                if receipt:
                    print(f"\n{'=' * 50}")
                    print("DONATION RECEIPT")
                    print(f"{'=' * 50}")
                    print(f"Receipt #: {receipt['receipt_number']}")
                    print(f"Date: {receipt['date']}")
                    print(f"Donor: {receipt['donor_name']}")
                    print(f"Item: {receipt['item_description']}")
                    print(f"Quantity: {receipt['quantity']}")
                    print(f"Estimated Value: \u00a3{receipt['estimated_value']:.2f}")
                    print(f"\n{receipt['statement']}")
                else:
                    print("Donation not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            donors = donor_database('list')
            print(f"\n{'=' * 60}")
            print("DONORS")
            print(f"{'=' * 60}")
            for d in donors:
                print(f"ID {d['id']}: {d['name']} - {d['total_donations']} donations, \u00a3{d['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '5':
            print("Categories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            cat_num = input("Category number: ").strip()
            print("Conditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
            cond_num = input("Condition number: ").strip()
            try:
                category = CATEGORIES[int(cat_num)-1]
                condition = CONDITIONS[int(cond_num)-1]
                value = donation_value_estimator(category, condition)
                print(f"\nEstimated Value: \u00a3{value:.2f}")
            except (ValueError, IndexError):
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            print("1. View Drive Summary  2. List All Drives")
            action = input("Choice: ").strip()
            if action == '1':
                drive_id = input("Drive ID: ").strip()
                summary = donation_drive_tracker('summary', drive_id=drive_id)
                print(f"\nDrive: {summary['drive_id']}")
                print(f"Donations: {summary['total_donations']}")
                print(f"Items: {summary['total_items']}")
                print(f"Value: \u00a3{summary['total_value']:.2f}")
            elif action == '2':
                drives = donation_drive_tracker('list_drives')
                print("\nDonation Drives:")
                for d in drives:
                    print(f"  {d['drive_id']}: {d['donations']} donations, \u00a3{d['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                donor_id = int(input("Donor ID: "))
                year = input("Year (optional): ").strip()
                year = int(year) if year else None
                letter = thank_you_letter_generator(donor_id, year)
                if letter:
                    print(letter['letter_text'])
                else:
                    print("Donor not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            year = input("Year (optional): ").strip()
            year = int(year) if year else None
            report = tax_deduction_report(year)
            print(f"\n{'=' * 60}")
            print(f"TAX DEDUCTION REPORT - {year or datetime.now().year}")
            print(f"{'=' * 60}")
            for r in report:
                print(f"{r['name']}: {r['donation_count']} donations, \u00a3{r['total_deductible']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '9':
            report = donor_contribution_report()
            print(f"\n{'=' * 60}")
            print("DONOR CONTRIBUTION REPORT")
            print(f"{'=' * 60}")
            for r in report:
                print(f"{r['name']}: {r['donation_count']} donations, {r['items_donated']} items, \u00a3{r['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '10':
            break


def staff_operations_cli() -> None:
    """Staff and operations submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       STAFF & OPERATIONS")
        print("=" * 50)
        print("1. Register Staff/Volunteer")
        print("2. View Staff")
        print("3. Staff Performance")
        print("4. Shift Scheduling")
        print("5. Volunteer Hours")
        print("6. Task Management")
        print("7. Opening Checklist")
        print("8. Closing Checklist")
        print("9. Cash Reconciliation")
        print("10. Manage Locations")
        print("11. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            role = input("Role (volunteer/staff/manager) [volunteer]: ").strip() or 'volunteer'
            staff_id = register_staff(name, email, phone, role)
            if staff_id:
                print(f"\n\u2705 Staff registered (ID: {staff_id})")
            input("\nPress Enter to continue...")

        elif choice == '2':
            staff = get_all_staff()
            print(f"\n{'=' * 60}")
            print("STAFF LIST")
            print(f"{'=' * 60}")
            for s in staff:
                print(f"ID {s['id']}: {s['name']} ({s['role']}) - Hours: {s['total_hours']:.1f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            staff = staff_performance_tracker()
            print(f"\n{'=' * 60}")
            print("STAFF PERFORMANCE (Last 30 Days)")
            print(f"{'=' * 60}")
            for s in staff:
                print(f"{s['name']} ({s['role']}): {s['sales_count']} sales, \u00a3{s['total_sales']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '4':
            print("1. Add Shift  2. View Date  3. View Staff Shifts")
            action = input("Choice: ").strip()
            if action == '1':
                try:
                    staff_id = int(input("Staff ID: "))
                    date = input("Date (YYYY-MM-DD): ").strip()
                    start = input("Start time (HH:MM): ").strip()
                    end = input("End time (HH:MM): ").strip()
                    shift_scheduling('add', staff_id=staff_id, date=date, start_time=start, end_time=end)
                    print("\u2705 Shift added!")
                except ValueError:
                    print("Invalid input.")
            elif action == '2':
                date = input("Date (YYYY-MM-DD): ").strip()
                shifts = shift_scheduling('view_date', date=date)
                print(f"\nShifts on {date}:")
                for s in shifts:
                    print(f"  {s['staff_name']}: {s['start_time']} - {s['end_time']} ({s['hours']:.1f}h)")
            elif action == '3':
                try:
                    staff_id = int(input("Staff ID: "))
                    shifts = shift_scheduling('view_staff', staff_id=staff_id)
                    print("\nRecent Shifts:")
                    for s in shifts:
                        print(f"  {s['date']}: {s['start_time']} - {s['end_time']} ({s['hours']:.1f}h)")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                staff_id = int(input("Staff ID: "))
                period = input("Period (week/month/year) [month]: ").strip() or 'month'
                hours = volunteer_hours_tracker(staff_id, period)
                if hours:
                    print(f"\n{hours['name']} ({hours['role']})")
                    print(f"Period: {hours['period']}")
                    print(f"Total Hours: {hours['total_hours']:.1f}")
                    print(f"Shifts: {hours['shift_count']}")
                    print(f"Average: {hours['average_hours']:.1f}h per shift")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            print("1. Create Task  2. View All Tasks  3. Update Status")
            action = input("Choice: ").strip()
            if action == '1':
                title = input("Task title: ").strip()
                desc = input("Description: ").strip()
                assigned = input("Assign to staff ID (optional): ").strip()
                priority = input("Priority (low/medium/high) [medium]: ").strip() or 'medium'
                due = input("Due date (YYYY-MM-DD): ").strip()
                assigned_to = int(assigned) if assigned else None
                task_id = task_assignment_system('create', title=title, description=desc,
                                                  assigned_to=assigned_to, priority=priority, due_date=due)
                print(f"\u2705 Task created (ID: {task_id})")
            elif action == '2':
                status = input("Status (pending/in_progress/completed) [pending]: ").strip() or 'pending'
                tasks = task_assignment_system('view_all', status=status)
                print(f"\nTasks ({status}):")
                for t in tasks:
                    print(f"  [{t['priority']}] {t['title']} - {t['staff_name']} (Due: {t['due_date']})")
            elif action == '3':
                try:
                    task_id = int(input("Task ID: "))
                    status = input("New status (pending/in_progress/completed): ").strip()
                    task_assignment_system('update_status', task_id=task_id, status=status)
                    print("\u2705 Status updated!")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            checklist = opening_closing_checklist('get', 'opening')
            print("\n--- OPENING CHECKLIST ---")
            for item in checklist['items']:
                status = input(f"[ ] {item['task']} (done? y/n): ").strip().lower()
                item['completed'] = status == 'y'
            completed = sum(1 for i in checklist['items'] if i['completed'])
            print(f"\n{completed}/{len(checklist['items'])} tasks completed")
            opening_closing_checklist('log', 'opening')
            input("\nPress Enter to continue...")

        elif choice == '8':
            checklist = opening_closing_checklist('get', 'closing')
            print("\n--- CLOSING CHECKLIST ---")
            for item in checklist['items']:
                status = input(f"[ ] {item['task']} (done? y/n): ").strip().lower()
                item['completed'] = status == 'y'
            completed = sum(1 for i in checklist['items'] if i['completed'])
            print(f"\n{completed}/{len(checklist['items'])} tasks completed")
            opening_closing_checklist('log', 'closing')
            input("\nPress Enter to continue...")

        elif choice == '9':
            try:
                opening = float(input("Opening float: \u00a3"))
                expected = float(input("Expected total: \u00a3"))
                actual = float(input("Actual total: \u00a3"))
                notes = input("Notes: ").strip()
                result = cash_register_reconciliation(opening, expected, actual, notes)
                print(f"\nStatus: {result['status'].upper()}")
                print(f"Difference: \u00a3{result['difference']:.2f}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            print("1. View Locations  2. Add Location")
            action = input("Choice: ").strip()
            if action == '1':
                locations = get_all_locations()
                print("\nLocations:")
                for loc in locations:
                    print(f"  ID {loc['id']}: {loc['name']} - {loc['address']}")
            elif action == '2':
                name = input("Location name: ").strip()
                address = input("Address: ").strip() or None
                phone = input("Phone: ").strip() or None
                manager = input("Manager: ").strip() or None
                loc_id = add_location(name, address, phone, manager)
                if loc_id:
                    print(f"\u2705 Location added (ID: {loc_id})")
            input("\nPress Enter to continue...")

        elif choice == '11':
            break
