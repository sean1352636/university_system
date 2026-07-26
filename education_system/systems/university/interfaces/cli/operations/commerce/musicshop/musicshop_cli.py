"""
Music Shop CLI Interface

Command-line interface for music shop management including
products, orders, payments, wishlists, and reporting.
"""

import csv
import os
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_db_connection
from education_system.systems.university.domain.operations.commerce.musicshop.services.musicshop_core import (
    init_musicshop_db,
    ProductManager,
    OrderManager,
    TransactionManager,
    WishlistManager,
    ReportManager,
    MUSIC_CATEGORIES,
    GENRES,
    ORDER_STATUSES,
    CONDITION_TYPES,
)


def display_menu():
    """Display the music shop menu and handle user input."""
    init_musicshop_db()

    while True:
        print("\n" + "=" * 70)
        print(" " * 22 + "MUSIC SHOP MANAGEMENT")
        print("=" * 70)

        print("\n[Products]")
        print("1.  Add Product")
        print("2.  View Product")
        print("3.  List All Products")
        print("4.  Browse by Category")
        print("5.  Browse by Genre")
        print("6.  Search Products")
        print("7.  Update Product")
        print("8.  Update Stock")
        print("9.  Low Stock Products")
        print("10. Rare/Collectible Items")

        print("\n[Orders]")
        print("11. Create Order")
        print("12. View Order")
        print("13. List Orders by Status")
        print("14. Customer Orders")
        print("15. Update Order Status")
        print("16. Cancel Order")

        print("\n[Payments]")
        print("17. Record Payment")
        print("18. Process Refund")

        print("\n[Wishlist]")
        print("19. Add to Wishlist")
        print("20. Remove from Wishlist")
        print("21. View Wishlist")

        print("\n[Reports]")
        print("22. Sales Summary")
        print("23. Inventory Summary")
        print("24. Sales by Genre")
        print("25. Top Selling Products")
        print("26. Top Artists")
        print("27. Full Admin Report")
        print("28. Email Admin Report")
        print("29. Export Transactions to CSV")

        print("\n0.  Back to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            if choice == "0":
                break
            elif choice == "1":
                _add_product()
            elif choice == "2":
                _view_product()
            elif choice == "3":
                _list_all_products()
            elif choice == "4":
                _browse_by_category()
            elif choice == "5":
                _browse_by_genre()
            elif choice == "6":
                _search_products()
            elif choice == "7":
                _update_product()
            elif choice == "8":
                _update_stock()
            elif choice == "9":
                _low_stock_products()
            elif choice == "10":
                _rare_items()
            elif choice == "11":
                _create_order()
            elif choice == "12":
                _view_order()
            elif choice == "13":
                _list_orders_by_status()
            elif choice == "14":
                _customer_orders()
            elif choice == "15":
                _update_order_status()
            elif choice == "16":
                _cancel_order()
            elif choice == "17":
                _record_payment()
            elif choice == "18":
                _process_refund()
            elif choice == "19":
                _add_to_wishlist()
            elif choice == "20":
                _remove_from_wishlist()
            elif choice == "21":
                _view_wishlist()
            elif choice == "22":
                _sales_summary()
            elif choice == "23":
                _inventory_summary()
            elif choice == "24":
                _sales_by_genre()
            elif choice == "25":
                _top_selling_products()
            elif choice == "26":
                _top_artists()
            elif choice == "27":
                _admin_report()
            elif choice == "28":
                _email_admin_report()
            elif choice == "29":
                _export_transactions_csv()
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")


def _add_product():
    """Add a new product."""
    print("\n--- Add Product ---")
    sku = input("SKU: ").strip()
    title = input("Title: ").strip()

    print(f"Categories: {', '.join(MUSIC_CATEGORIES)}")
    category = input("Category: ").strip()

    price = float(input("Price: ").strip())
    artist = input("Artist (optional): ").strip() or None

    print(f"Genres: {', '.join(GENRES)}")
    genre = input("Genre (optional): ").strip() or None

    format_type = input("Format (e.g. Vinyl, CD, Cassette, optional): ").strip() or None
    label = input("Label (optional): ").strip() or None
    year_str = input("Release year (optional): ").strip()
    release_year = int(year_str) if year_str else None

    print(f"Conditions: {', '.join(CONDITION_TYPES)}")
    condition = input("Condition (default 'new'): ").strip() or "new"

    description = input("Description (optional): ").strip() or None
    cost_str = input("Cost price (optional): ").strip()
    cost_price = float(cost_str) if cost_str else None
    stock_str = input("Stock quantity (default 0): ").strip()
    stock_quantity = int(stock_str) if stock_str else 0
    is_rare_str = input("Is rare/collectible? (y/n, default n): ").strip().lower()
    is_rare = is_rare_str == "y"

    product_id = ProductManager.add_product(
        sku, title, category, price,
        artist=artist, genre=genre, format=format_type, label=label,
        release_year=release_year, condition=condition,
        description=description, cost_price=cost_price,
        stock_quantity=stock_quantity, is_rare=is_rare,
    )
    if product_id:
        print(f"Product added successfully. Product ID: {product_id}")
    else:
        print("Failed to add product. SKU may already exist.")


def _view_product():
    """View product details."""
    print("\n--- View Product ---")
    product_id = int(input("Product ID: ").strip())

    product = ProductManager.get_product(product_id)
    if not product:
        print("Product not found.")
        return

    print(f"\n  Product ID:    {product['product_id']}")
    print(f"  SKU:           {product['sku']}")
    print(f"  Title:         {product['name']}")
    print(f"  Artist:        {product.get('artist', 'N/A')}")
    print(f"  Category:      {product['category']}")
    print(f"  Genre:         {product.get('genre', 'N/A')}")
    print(f"  Format:        {product.get('format', 'N/A')}")
    print(f"  Label:         {product.get('label', 'N/A')}")
    print(f"  Year:          {product.get('release_year', 'N/A')}")
    print(f"  Condition:     {product.get('condition', 'N/A')}")
    print(f"  Price:         £{product['price']:.2f}")
    print(f"  Cost Price:    £{product.get('cost_price', 0):.2f}" if product.get('cost_price') else "  Cost Price:    N/A")
    print(f"  Stock:         {product.get('stock_quantity', 0)}")
    print(f"  Min Stock:     {product.get('min_stock_level', 0)}")
    print(f"  Rare:          {'Yes' if product.get('is_rare') else 'No'}")
    print(f"  Active:        {'Yes' if product.get('is_active') else 'No'}")


def _list_all_products():
    """List all products."""
    print("\n--- All Products ---")
    products = ProductManager.get_all_products()
    if not products:
        print("No products found.")
        return

    print(f"\n{'ID':<6}{'SKU':<15}{'Title':<25}{'Artist':<18}{'Price':<10}{'Stock':<8}")
    print("-" * 82)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['sku']:<15}{p['name']:<25}"
            f"{(p.get('artist') or 'N/A'):<18}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _browse_by_category():
    """Browse products by category."""
    print("\n--- Browse by Category ---")
    print(f"Categories: {', '.join(MUSIC_CATEGORIES)}")
    category = input("Category: ").strip()

    products = ProductManager.get_products_by_category(category)
    if not products:
        print("No products found in this category.")
        return

    print(f"\n{'ID':<6}{'Title':<25}{'Artist':<18}{'Price':<10}{'Stock':<8}")
    print("-" * 67)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['name']:<25}"
            f"{(p.get('artist') or 'N/A'):<18}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _browse_by_genre():
    """Browse products by genre."""
    print("\n--- Browse by Genre ---")
    print(f"Genres: {', '.join(GENRES)}")
    genre = input("Genre: ").strip()

    products = ProductManager.get_products_by_genre(genre)
    if not products:
        print("No products found in this genre.")
        return

    print(f"\n{'ID':<6}{'Title':<25}{'Artist':<18}{'Price':<10}{'Stock':<8}")
    print("-" * 67)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['name']:<25}"
            f"{(p.get('artist') or 'N/A'):<18}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _search_products():
    """Search products."""
    print("\n--- Search Products ---")
    query = input("Search term (name, artist, genre, SKU): ").strip()

    products = ProductManager.search_products(query)
    if not products:
        print("No products found.")
        return

    print(f"\n{'ID':<6}{'SKU':<15}{'Title':<25}{'Artist':<18}{'Price':<10}{'Stock':<8}")
    print("-" * 82)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['sku']:<15}{p['name']:<25}"
            f"{(p.get('artist') or 'N/A'):<18}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _update_product():
    """Update a product."""
    print("\n--- Update Product ---")
    product_id = int(input("Product ID: ").strip())

    product = ProductManager.get_product(product_id)
    if not product:
        print("Product not found.")
        return

    print(f"Current: {product['name']} | £{product['price']:.2f} | Stock: {product.get('stock_quantity', 0)}")
    print("Press Enter to keep current value.")

    updates = {}
    name = input(f"Title [{product['name']}]: ").strip()
    if name:
        updates['name'] = name
    price = input(f"Price [{product['price']}]: ").strip()
    if price:
        updates['price'] = float(price)
    description = input("Description: ").strip()
    if description:
        updates['description'] = description
    condition = input(f"Condition [{product.get('condition', '')}]: ").strip()
    if condition:
        updates['condition'] = condition

    if updates:
        if ProductManager.update_product(product_id, **updates):
            print("Product updated successfully.")
        else:
            print("Failed to update product.")
    else:
        print("No changes made.")


def _update_stock():
    """Update product stock."""
    print("\n--- Update Stock ---")
    product_id = int(input("Product ID: ").strip())
    change = int(input("Quantity change (positive to add, negative to remove): ").strip())

    if ProductManager.update_stock(product_id, change):
        print("Stock updated successfully.")
    else:
        print("Failed to update stock.")


def _low_stock_products():
    """Display low stock products."""
    print("\n--- Low Stock Products ---")
    products = ProductManager.get_low_stock_products()
    if not products:
        print("No low stock products.")
        return

    print(f"\n{'ID':<6}{'Title':<25}{'Stock':<8}{'Min':<8}{'Price':<10}")
    print("-" * 57)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['name']:<25}{p.get('stock_quantity', 0):<8}"
            f"{p.get('min_stock_level', 0):<8}£{p['price']:<9.2f}"
        )


def _rare_items():
    """Display rare/collectible items."""
    print("\n--- Rare/Collectible Items ---")
    items = ProductManager.get_rare_items()
    if not items:
        print("No rare items found.")
        return

    print(f"\n{'ID':<6}{'Title':<25}{'Artist':<18}{'Condition':<12}{'Price':<10}{'Stock':<8}")
    print("-" * 79)
    for p in items:
        print(
            f"{p['product_id']:<6}{p['name']:<25}{(p.get('artist') or 'N/A'):<18}"
            f"{p.get('condition', 'N/A'):<12}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _create_order():
    """Create a new order."""
    print("\n--- Create Order ---")
    customer_id = input("Customer ID: ").strip()
    customer_name = input("Customer name: ").strip()
    customer_email = input("Customer email (optional): ").strip() or None
    shipping_address = input("Shipping address (optional): ").strip() or None
    payment_method = input("Payment method (card/cash/transfer, optional): ").strip() or None

    items = []
    while True:
        print("\nAdd item (Enter blank product ID to finish):")
        pid_str = input("  Product ID: ").strip()
        if not pid_str:
            break

        product_id = int(pid_str)
        product = ProductManager.get_product(product_id)
        if not product:
            print("  Product not found.")
            continue

        print(f"  {product['name']} by {product.get('artist', 'N/A')} - £{product['price']:.2f}")
        qty = int(input("  Quantity: ").strip())

        items.append({
            'product_id': product_id,
            'product_title': product['name'],
            'artist': product.get('artist'),
            'unit_price': product['price'],
            'quantity': qty,
        })

    if not items:
        print("No items added. Order cancelled.")
        return

    order_id = OrderManager.create_order(
        customer_id, customer_name, items,
        customer_email=customer_email,
        shipping_address=shipping_address,
        payment_method=payment_method,
    )
    if order_id:
        order = OrderManager.get_order(order_id)
        print("\nOrder created successfully!")
        print(f"  Order ID:     {order_id}")
        print(f"  Order #:      {order['order_number']}")
        print(f"  Subtotal:     £{order['subtotal']:.2f}")
        print(f"  Tax:          £{order['tax_amount']:.2f}")
        print(f"  Total:        £{order['total_amount']:.2f}")
    else:
        print("Failed to create order.")


def _view_order():
    """View order details."""
    print("\n--- View Order ---")
    order_id = int(input("Order ID: ").strip())

    order = OrderManager.get_order(order_id)
    if not order:
        print("Order not found.")
        return

    print(f"\n  Order ID:       {order['order_id']}")
    print(f"  Order #:        {order['order_number']}")
    print(f"  Customer:       {order['customer_name']} ({order['customer_id']})")
    print(f"  Email:          {order.get('customer_email', 'N/A')}")
    print(f"  Address:        {order.get('shipping_address', 'N/A')}")
    print(f"  Subtotal:       £{order['subtotal']:.2f}")
    print(f"  Tax:            £{order['tax_amount']:.2f}")
    print(f"  Shipping:       £{order.get('shipping_fee', 0):.2f}")
    print(f"  Discount:       £{order.get('discount_amount', 0):.2f}")
    print(f"  Total:          £{order['total_amount']:.2f}")
    print(f"  Order Status:   {order['order_status']}")
    print(f"  Payment Status: {order['payment_status']}")
    print(f"  Payment Method: {order.get('payment_method', 'N/A')}")
    print(f"  Created:        {order.get('created_at', 'N/A')}")

    if order.get('items'):
        print("\n  Items:")
        for item in order['items']:
            print(
                f"    - {item['item_name']} "
                f"({item.get('artist', 'N/A')}) x{item['quantity']} "
                f"@ £{item['unit_price']:.2f} = £{item['subtotal']:.2f}"
            )


def _list_orders_by_status():
    """List orders by status."""
    print("\n--- List Orders by Status ---")
    print(f"Statuses: {', '.join(ORDER_STATUSES)}")
    status = input("Status: ").strip()

    orders = OrderManager.get_orders_by_status(status)
    if not orders:
        print("No orders found.")
        return

    print(f"\n{'ID':<6}{'Order #':<22}{'Customer':<20}{'Total':<12}{'Status':<12}")
    print("-" * 72)
    for o in orders:
        print(
            f"{o['order_id']:<6}{o['order_number']:<22}{o['customer_name']:<20}"
            f"£{o['total_amount']:<11.2f}{o['order_status']:<12}"
        )


def _customer_orders():
    """View customer orders."""
    print("\n--- Customer Orders ---")
    customer_id = input("Customer ID: ").strip()

    orders = OrderManager.get_customer_orders(customer_id)
    if not orders:
        print("No orders found.")
        return

    print(f"\n{'ID':<6}{'Order #':<22}{'Total':<12}{'Status':<12}{'Date':<12}")
    print("-" * 64)
    for o in orders:
        print(
            f"{o['order_id']:<6}{o['order_number']:<22}£{o['total_amount']:<11.2f}"
            f"{o['order_status']:<12}{str(o.get('created_at', 'N/A'))[:10]:<12}"
        )


def _update_order_status():
    """Update order status."""
    print("\n--- Update Order Status ---")
    order_id = int(input("Order ID: ").strip())
    print(f"Statuses: {', '.join(ORDER_STATUSES)}")
    status = input("New status: ").strip()

    if OrderManager.update_order_status(order_id, status):
        print("Order status updated successfully.")
    else:
        print("Failed to update order status.")


def _cancel_order():
    """Cancel an order."""
    print("\n--- Cancel Order ---")
    order_id = int(input("Order ID: ").strip())
    reason = input("Reason (optional): ").strip() or None
    confirm = input("Confirm cancellation? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if OrderManager.cancel_order(order_id, reason):
        print("Order cancelled successfully. Stock restored.")
    else:
        print("Failed to cancel order.")


def _record_payment():
    """Record a payment for an order."""
    print("\n--- Record Payment ---")
    order_id = int(input("Order ID: ").strip())
    customer_id = input("Customer ID: ").strip()
    amount = float(input("Amount: ").strip())
    payment_method = input("Payment method (card/cash/transfer): ").strip()

    txn_id = TransactionManager.record_payment(order_id, customer_id, amount, payment_method)
    if txn_id:
        print(f"Payment recorded. Transaction ID: {txn_id}")
    else:
        print("Failed to record payment.")


def _process_refund():
    """Process a refund."""
    print("\n--- Process Refund ---")
    order_id = int(input("Order ID: ").strip())
    amount = float(input("Refund amount: ").strip())
    reason = input("Reason (optional): ").strip() or None
    confirm = input("Confirm refund? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    txn_id = TransactionManager.process_refund(order_id, amount, reason)
    if txn_id:
        print(f"Refund processed. Transaction ID: {txn_id}")
    else:
        print("Failed to process refund.")


def _add_to_wishlist():
    """Add product to wishlist."""
    print("\n--- Add to Wishlist ---")
    customer_id = input("Customer ID: ").strip()
    product_id = int(input("Product ID: ").strip())

    if WishlistManager.add_to_wishlist(customer_id, product_id):
        print("Product added to wishlist.")
    else:
        print("Failed to add to wishlist.")


def _remove_from_wishlist():
    """Remove product from wishlist."""
    print("\n--- Remove from Wishlist ---")
    customer_id = input("Customer ID: ").strip()
    product_id = int(input("Product ID: ").strip())

    if WishlistManager.remove_from_wishlist(customer_id, product_id):
        print("Product removed from wishlist.")
    else:
        print("Failed to remove from wishlist.")


def _view_wishlist():
    """View customer wishlist."""
    print("\n--- Customer Wishlist ---")
    customer_id = input("Customer ID: ").strip()

    products = WishlistManager.get_wishlist(customer_id)
    if not products:
        print("Wishlist is empty.")
        return

    print(f"\n{'ID':<6}{'Title':<25}{'Artist':<18}{'Price':<10}{'Stock':<8}")
    print("-" * 67)
    for p in products:
        print(
            f"{p['product_id']:<6}{p['name']:<25}"
            f"{(p.get('artist') or 'N/A'):<18}£{p['price']:<9.2f}{p.get('stock_quantity', 0):<8}"
        )


def _sales_summary():
    """Display sales summary."""
    print("\n--- Sales Summary ---")
    summary = ReportManager.get_sales_summary()
    if not summary:
        print("No data available.")
        return

    print(f"  Total Orders:      {summary.get('total_orders', 0)}")
    print(f"  Total Revenue:     £{summary.get('total_revenue', 0):.2f}")
    print(f"  Avg Order Value:   £{summary.get('avg_order_value', 0):.2f}")
    print(f"  Pending Orders:    {summary.get('pending_orders', 0)}")
    print(f"  Completed Orders:  {summary.get('completed_orders', 0)}")


def _inventory_summary():
    """Display inventory summary."""
    print("\n--- Inventory Summary ---")
    summary = ReportManager.get_inventory_summary()
    if not summary:
        print("No data available.")
        return

    print(f"  Total Products:    {summary.get('total_products', 0)}")
    print(f"  Total Stock:       {summary.get('total_stock', 0)}")
    print(f"  Total Value:       £{summary.get('total_value', 0):.2f}")
    print(f"  Low Stock Items:   {summary.get('low_stock_count', 0)}")
    print(f"  Rare Items:        {summary.get('rare_items_count', 0)}")


def _sales_by_genre():
    """Display sales by genre."""
    print("\n--- Sales by Genre ---")
    data = ReportManager.get_sales_by_genre()
    if not data:
        print("No data available.")
        return

    print(f"\n{'Genre':<18}{'Items Sold':<14}{'Revenue':<12}")
    print("-" * 44)
    for g in data:
        print(
            f"{g['genre']:<18}{g.get('items_sold', 0):<14}£{g.get('revenue', 0):.2f}"
        )


def _top_selling_products():
    """Display top selling products."""
    print("\n--- Top Selling Products ---")
    limit_str = input("How many (default 10): ").strip()
    limit = int(limit_str) if limit_str else 10

    products = ReportManager.get_top_selling_products(limit)
    if not products:
        print("No data available.")
        return

    for i, p in enumerate(products, 1):
        print(
            f"  {i}. {p['name']} by {p.get('artist', 'Unknown')} - "
            f"Sold: {p.get('total_sold', 0)}, Revenue: £{p.get('total_revenue', 0):.2f}"
        )


def _top_artists():
    """Display top artists."""
    print("\n--- Top Artists ---")
    limit_str = input("How many (default 10): ").strip()
    limit = int(limit_str) if limit_str else 10

    artists = ReportManager.get_top_artists(limit)
    if not artists:
        print("No data available.")
        return

    for i, a in enumerate(artists, 1):
        print(
            f"  {i}. {a['artist']} - "
            f"Revenue: £{a.get('revenue', 0):.2f}, "
            f"Items Sold: {a.get('items_sold', 0)}, "
            f"Orders: {a.get('orders', 0)}"
        )


def _admin_report():
    """Display full admin report."""
    print(ReportManager.generate_admin_report())


def _email_admin_report():
    """Email the full admin report to an admin user."""
    from education_system.systems.university.infrastructure.email.email_service import send_email

    print("\n--- Email Admin Report ---")
    report = ReportManager.generate_admin_report()

    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
        )
        result = cursor.fetchone()

    if not result or not result[0]:
        print("No admin email address found. Report not sent.")
        return

    recipient_email = result[0]
    report_date = datetime.now().strftime('%Y-%m-%d')
    send_email(
        recipient_email=recipient_email,
        subject=f"Music Shop Admin Report - {report_date}",
        body=report,
    )
    print(f"Admin report emailed to {recipient_email}.")


def _export_transactions_csv():
    """Export music shop transactions to a CSV file."""
    print("\n--- Export Transactions to CSV ---")

    default_path = os.path.abspath(
        f"musicshop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    file_path = input(f"File path [{default_path}]: ").strip() or default_path
    file_path = os.path.abspath(file_path)

    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT transaction_id, reference_id as order_id, created_at, customer_id,
                   amount, payment_method, status
            FROM transactions
            WHERE source_type = 'music_shop'
            ORDER BY created_at DESC
            LIMIT 500
        ''')
        transactions = cursor.fetchall()

    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Transaction ID', 'Order ID', 'Date', 'Customer',
                         'Amount', 'Payment Method', 'Status'])
        for trans in transactions:
            trans_id, order_id, created_at, customer_id, amount, payment_method, status = trans
            payment_display = payment_method.replace('_', ' ').title() if payment_method else 'N/A'
            status_display = status.upper() if status else 'COMPLETED'
            writer.writerow([
                trans_id, order_id, created_at, customer_id or 'N/A',
                f"£{amount:.2f}", payment_display, status_display,
            ])

    print(f"Exported {len(transactions)} transaction(s) to:\n  {file_path}")


if __name__ == "__main__":
    display_menu()
