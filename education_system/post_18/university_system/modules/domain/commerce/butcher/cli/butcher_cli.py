"""
Butcher Shop CLI Interface

Provides command-line interface for butcher shop management including:
- Product management (add, list, update, stock)
- Order management (create, view, status updates)
- Payment processing (pay, refund)
- Supplier orders
- Reports and analytics
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.commerce.butcher.services.butcher_core import (
    ProductManager,
    OrderManager,
    TransactionManager,
    ReportManager,
    init_butcher_db,
    MEAT_CATEGORIES,
    UNIT_TYPES,
    ORDER_STATUSES,
)


class ButcherCLI:
    """Command-line interface for the Butcher Shop."""

    def __init__(self):
        """Initialize the Butcher CLI and database."""
        init_butcher_db()

    def run(self):
        """Run the butcher CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._products_menu()
            elif choice == '2':
                self._orders_menu()
            elif choice == '3':
                self._payments_menu()
            elif choice == '4':
                self._reports_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  BUTCHER SHOP MANAGEMENT SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Products & Inventory")
        print("  2. Orders")
        print("  3. Payments & Transactions")
        print("  4. Reports")
        print("  0. Back to Main Menu")

    # ========== Products ==========

    def _products_menu(self):
        """Products sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PRODUCTS & INVENTORY")
            print("-" * 50)
            print("  1. Add Product")
            print("  2. List Products")
            print("  3. View Product")
            print("  4. Update Product")
            print("  5. Update Stock")
            print("  6. Low Stock Alert")
            print("  7. Search Products")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_product()
                elif choice == '2':
                    self._list_products()
                elif choice == '3':
                    self._view_product()
                elif choice == '4':
                    self._update_product()
                elif choice == '5':
                    self._update_stock()
                elif choice == '6':
                    self._low_stock()
                elif choice == '7':
                    self._search_products()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_product(self):
        """Add a new product."""
        print("\n--- Add New Product ---")
        print(f"Categories: {', '.join(MEAT_CATEGORIES.keys())}")
        name = input("Product name: ").strip()
        category = input("Category: ").strip()
        price = float(input("Price per unit: ").strip())
        print(f"Unit types: {', '.join(UNIT_TYPES)}")
        unit_type = input("Unit type [kg]: ").strip() or 'kg'
        description = input("Description (optional): ").strip() or None
        stock = input("Initial stock quantity [0]: ").strip()
        stock_quantity = float(stock) if stock else 0
        origin = input("Origin (optional): ").strip() or None
        storage = input("Storage temp (optional): ").strip() or None
        shelf = input("Shelf life days (optional): ").strip()
        shelf_life = int(shelf) if shelf else None

        product_id = ProductManager.add_product(
            name=name, category=category, price_per_unit=price,
            unit_type=unit_type, description=description,
            stock_quantity=stock_quantity, origin=origin,
            storage_temp=storage, shelf_life_days=shelf_life,
        )
        print(f"\nProduct added (ID: {product_id})")

    def _list_products(self):
        """List products."""
        cat = input("Filter by category (blank for all): ").strip() or None
        show_all = input("Include unavailable? (y/n) [n]: ").strip().lower() == 'y'
        products = ProductManager.get_all_products(category=cat, available_only=not show_all)
        if not products:
            print("\nNo products found.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Category':<12}{'Price':<10}{'Stock':<10}{'Unit'}")
        print("-" * 75)
        for p in products:
            print(f"{p['source_product_id']:<6}{p['name']:<25}"
                  f"{p['category']:<12}{p['price_per_unit']:<10.2f}"
                  f"{p['stock_quantity']:<10.1f}{p['unit_type']}")

    def _view_product(self):
        """View product details."""
        product_id = int(input("Product ID: ").strip())
        product = ProductManager.get_product(product_id)
        if not product:
            print("Product not found.")
            return
        print(f"\nID: {product['source_product_id']}")
        print(f"Name: {product['name']}")
        print(f"Category: {product['category']}")
        print(f"Description: {product.get('description', 'N/A')}")
        print(f"Price: {product['price_per_unit']:.2f} per {product['unit_type']}")
        print(f"Stock: {product['stock_quantity']} {product['unit_type']}")
        print(f"Min Stock Level: {product.get('min_stock_level', 'N/A')}")
        print(f"Origin: {product.get('origin', 'N/A')}")
        print(f"Storage Temp: {product.get('storage_temp', 'N/A')}")
        print(f"Shelf Life: {product.get('shelf_life_days', 'N/A')} days")
        print(f"Available: {'Yes' if product.get('is_available') else 'No'}")

    def _update_product(self):
        """Update product."""
        product_id = int(input("Product ID: ").strip())
        print("Leave blank to keep current value:")
        name = input("Name: ").strip() or None
        price_input = input("Price per unit: ").strip()
        price = float(price_input) if price_input else None
        cat = input("Category: ").strip() or None
        desc = input("Description: ").strip() or None

        kwargs = {}
        if name:
            kwargs['name'] = name
        if price is not None:
            kwargs['price_per_unit'] = price
        if cat:
            kwargs['category'] = cat
        if desc:
            kwargs['description'] = desc

        updated = ProductManager.update_product(product_id, **kwargs)
        print("Product updated." if updated else "No changes made.")

    def _update_stock(self):
        """Update product stock."""
        product_id = int(input("Product ID: ").strip())
        change = float(input("Quantity change (+ to add, - to subtract): ").strip())
        reason = input("Reason: ").strip()
        user_id = input("User ID (optional): ").strip() or None

        updated = ProductManager.update_stock(product_id, change, reason, user_id)
        print("Stock updated." if updated else "Failed to update stock.")

    def _low_stock(self):
        """Show low stock products."""
        products = ProductManager.get_low_stock_products()
        if not products:
            print("\nNo low stock items.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Category':<12}{'Stock':<10}{'Min Level':<10}{'Unit'}")
        print("-" * 75)
        for p in products:
            print(f"{p['source_product_id']:<6}{p['name']:<25}"
                  f"{p['category']:<12}{p['stock_quantity']:<10.1f}"
                  f"{p.get('min_stock_level', 0):<10.1f}{p['unit_type']}")

    def _search_products(self):
        """Search products."""
        term = input("Search term: ").strip()
        products = ProductManager.search_products(term)
        if not products:
            print("\nNo products found.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Category':<12}{'Price':<10}{'Stock':<10}")
        print("-" * 65)
        for p in products:
            print(f"{p['source_product_id']:<6}{p['name']:<25}"
                  f"{p['category']:<12}{p['price_per_unit']:<10.2f}"
                  f"{p['stock_quantity']:<10.1f}")

    # ========== Orders ==========

    def _orders_menu(self):
        """Orders sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  ORDER MANAGEMENT")
            print("-" * 50)
            print("  1. Create Order")
            print("  2. Add Item to Order")
            print("  3. View Order")
            print("  4. Lookup by Order Number")
            print("  5. Update Order Status")
            print("  6. Update Payment Status")
            print("  7. Orders by Status")
            print("  8. Customer Orders")
            print("  9. Today's Orders")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_order()
                elif choice == '2':
                    self._add_order_item()
                elif choice == '3':
                    self._view_order()
                elif choice == '4':
                    self._lookup_order()
                elif choice == '5':
                    self._update_order_status()
                elif choice == '6':
                    self._update_payment_status()
                elif choice == '7':
                    self._orders_by_status()
                elif choice == '8':
                    self._customer_orders()
                elif choice == '9':
                    self._todays_orders()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_order(self):
        """Create a new order."""
        print("\n--- Create Order ---")
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        customer_email = input("Email (optional): ").strip() or None
        customer_phone = input("Phone (optional): ").strip() or None
        order_type = input("Order type (counter/phone/online) [counter]: ").strip() or 'counter'
        pickup_date = input("Pickup date (YYYY-MM-DD, optional): ").strip() or None
        pickup_time = input("Pickup time (HH:MM, optional): ").strip() or None
        instructions = input("Special instructions (optional): ").strip() or None

        order_id, order_number = OrderManager.create_order(
            customer_id=customer_id, customer_name=customer_name,
            customer_email=customer_email, customer_phone=customer_phone,
            order_type=order_type, pickup_date=pickup_date,
            pickup_time=pickup_time, special_instructions=instructions,
        )
        print("\nOrder created!")
        print(f"  ID: {order_id}")
        print(f"  Number: {order_number}")

    def _add_order_item(self):
        """Add item to an order."""
        order_id = int(input("Order ID: ").strip())
        product_id = int(input("Product ID: ").strip())
        quantity = float(input("Quantity: ").strip())
        special_cut = input("Special cut (optional): ").strip() or None
        notes = input("Notes (optional): ").strip() or None

        item_id = OrderManager.add_order_item(
            order_id=order_id, product_id=product_id, quantity=quantity,
            special_cut=special_cut, notes=notes,
        )
        print(f"\nItem added (ID: {item_id})")

    def _view_order(self):
        """View order details."""
        order_id = int(input("Order ID: ").strip())
        order = OrderManager.get_order(order_id)
        if not order:
            print("Order not found.")
            return
        self._print_order(order)

    def _lookup_order(self):
        """Lookup order by number."""
        order_number = input("Order number: ").strip()
        order = OrderManager.get_order_by_number(order_number)
        if not order:
            print("Order not found.")
            return
        self._print_order(order)

    def _print_order(self, order):
        """Print order details."""
        print(f"\nOrder #{order.get('order_number', 'N/A')}")
        print(f"  Customer: {order['customer_name']}")
        print(f"  Type: {order.get('order_type', 'N/A')}")
        print(f"  Status: {order.get('order_status', 'N/A')}")
        print(f"  Payment: {order.get('payment_status', 'N/A')}")
        print(f"  Total: {(order.get('total_amount') or 0):.2f}")
        if order.get('pickup_date'):
            print(f"  Pickup: {order['pickup_date']} {order.get('pickup_time', '')}")
        if order.get('special_instructions'):
            print(f"  Instructions: {order['special_instructions']}")

        items = order.get('items', [])
        if items:
            print("\n  Items:")
            for item in items:
                print(f"    {item['item_name']}: {item['quantity']} {item.get('unit_type', '')} "
                      f"@ {item['unit_price']:.2f} = {item['subtotal']:.2f}"
                      + (f" [{item['special_cut']}]" if item.get('special_cut') else ""))

    def _update_order_status(self):
        """Update order status."""
        order_id = int(input("Order ID: ").strip())
        print(f"Statuses: {', '.join(ORDER_STATUSES)}")
        status = input("New status: ").strip()
        updated = OrderManager.update_order_status(order_id, status)
        print("Status updated." if updated else "Invalid status.")

    def _update_payment_status(self):
        """Update payment status."""
        order_id = int(input("Order ID: ").strip())
        payment_status = input("Payment status (pending/paid/refunded): ").strip()
        payment_method = input("Payment method (optional): ").strip() or None
        updated = OrderManager.update_payment_status(order_id, payment_status, payment_method)
        print("Payment status updated." if updated else "Failed to update.")

    def _orders_by_status(self):
        """View orders by status."""
        print(f"Statuses: {', '.join(ORDER_STATUSES)}")
        status = input("Status: ").strip()
        orders = OrderManager.get_orders_by_status(status)
        self._display_orders(orders)

    def _customer_orders(self):
        """View customer orders."""
        customer_id = input("Customer ID: ").strip()
        orders = OrderManager.get_customer_orders(customer_id)
        self._display_orders(orders)

    def _todays_orders(self):
        """View today's orders."""
        orders = OrderManager.get_todays_orders()
        self._display_orders(orders)

    def _display_orders(self, orders):
        """Display a list of orders."""
        if not orders:
            print("\nNo orders found.")
            return
        print(f"\n{'ID':<6}{'Number':<22}{'Customer':<20}{'Status':<12}{'Total':<10}{'Payment'}")
        print("-" * 80)
        for o in orders:
            print(f"{o['order_id']:<6}{o['order_number']:<22}{o['customer_name']:<20}"
                  f"{o.get('order_status', ''):<12}"
                  f"{(o.get('total_amount') or 0):<10.2f}"
                  f"{o.get('payment_status', '')}")

    # ========== Payments ==========

    def _payments_menu(self):
        """Payments sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PAYMENTS & TRANSACTIONS")
            print("-" * 50)
            print("  1. Process Payment")
            print("  2. Process Refund")
            print("  3. View Transaction")
            print("  4. Mark Receipt Sent")
            print("  5. Daily Sales")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._process_payment()
                elif choice == '2':
                    self._process_refund()
                elif choice == '3':
                    self._view_transaction()
                elif choice == '4':
                    self._mark_receipt()
                elif choice == '5':
                    self._daily_sales()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _process_payment(self):
        """Process a payment."""
        print("\n--- Process Payment ---")
        order_id = int(input("Order ID: ").strip())
        amount = float(input("Amount: ").strip())
        payment_method = input("Payment method (cash/card/contactless): ").strip()
        customer_id = input("Customer ID: ").strip()
        ref = input("Reference number (optional): ").strip() or None

        txn_id = TransactionManager.process_payment(
            order_id=order_id, amount=amount, payment_method=payment_method,
            customer_id=customer_id, reference_number=ref,
        )
        print(f"\nPayment processed (Transaction ID: {txn_id})")

    def _process_refund(self):
        """Process a refund."""
        order_id = int(input("Order ID: ").strip())
        amount = float(input("Refund amount: ").strip())
        reason = input("Reason: ").strip()
        customer_id = input("Customer ID: ").strip()

        txn_id = TransactionManager.process_refund(
            order_id=order_id, amount=amount, reason=reason,
            customer_id=customer_id,
        )
        print(f"\nRefund processed (Transaction ID: {txn_id})")

    def _view_transaction(self):
        """View transaction."""
        txn_id = int(input("Transaction ID: ").strip())
        txn = TransactionManager.get_transaction(txn_id)
        if not txn:
            print("Transaction not found.")
            return
        print(f"\nTransaction ID: {txn['transaction_id']}")
        print(f"Amount: {txn['amount']:.2f}")
        print(f"Payment Method: {txn['payment_method']}")
        print(f"Status: {txn['status']}")
        print(f"Date: {txn['created_at']}")

    def _mark_receipt(self):
        """Mark receipt as sent."""
        txn_id = int(input("Transaction ID: ").strip())
        TransactionManager.mark_receipt_sent(txn_id)
        print("Receipt marked as sent.")

    def _daily_sales(self):
        """Show daily sales."""
        date = input(f"Date [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() or None
        sales = TransactionManager.get_daily_sales(date)
        print(f"\nSales for {sales['date']}:")
        print(f"  Transactions: {sales['transaction_count']}")
        print(f"  Total Sales: {sales['total_sales']:.2f}")
        print(f"  Refunds: {sales['total_refunds']:.2f}")
        print(f"  Net Sales: {sales['net_sales']:.2f}")

    # ========== Reports ==========

    def _reports_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  REPORTS & ANALYTICS")
            print("-" * 50)
            print("  1. Sales Report")
            print("  2. Inventory Report")
            print("  3. Admin Report")
            print("  4. Email Admin Report")
            print("  5. Export Orders CSV")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._sales_report()
                elif choice == '2':
                    self._inventory_report()
                elif choice == '3':
                    self._admin_report()
                elif choice == '4':
                    self._email_admin_report()
                elif choice == '5':
                    self._export_orders_csv()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _sales_report(self):
        """Generate sales report."""
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()
        report = ReportManager.generate_sales_report(start_date, end_date)

        summary = report.get('summary', {})
        print(f"\n--- Sales Report ({start_date} to {end_date}) ---")
        print(f"Total Orders: {summary.get('total_orders', 0)}")
        print(f"Total Revenue: {(summary.get('total_revenue') or 0):.2f}")
        print(f"Avg Order Value: {(summary.get('avg_order_value') or 0):.2f}")

        if report.get('by_category'):
            print("\nBy Category:")
            for c in report['by_category']:
                print(f"  {c['category']}: {c['total_quantity']:.1f} units ({(c['total_sales'] or 0):.2f})")

        if report.get('top_products'):
            print("\nTop Products:")
            for i, p in enumerate(report['top_products'], 1):
                print(f"  {i}. {p['product_name']}: {p['total_quantity']:.1f} units ({(p['total_sales'] or 0):.2f})")

    def _inventory_report(self):
        """Generate inventory report."""
        report = ReportManager.generate_inventory_report()
        summary = report.get('summary', {})
        print("\n--- Inventory Report ---")
        print(f"Total Products: {summary.get('total_products', 0)}")
        print(f"Total Stock Value: {(summary.get('total_stock_value') or 0):.2f}")
        print(f"Low Stock Items: {summary.get('low_stock_count', 0)}")

        products = report.get('products', [])
        if products:
            print(f"\n{'ID':<6}{'Name':<25}{'Category':<12}{'Stock':<10}{'Value'}")
            print("-" * 60)
            for p in products:
                print(f"{p['product_id']:<6}{p['name']:<25}"
                      f"{p['category']:<12}{p['stock_quantity']:<10.1f}"
                      f"{(p['stock_value'] or 0):.2f}")

    def _admin_report(self):
        """Generate admin report."""
        report = ReportManager.generate_admin_report()
        print(report)

    def _email_admin_report(self):
        """Email the admin report to an admin user (same report the GUI emails)."""
        from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
        from education_system.post_18.university_system.infrastructure.email.email_service import send_email

        report = ReportManager.generate_admin_report()

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE role='admin' AND email IS NOT NULL LIMIT 1"
            ).fetchone()

        admin_email = row[0] if row else None
        if not admin_email:
            print("No admin email found. Cannot send report.")
            return

        subject = f"Butcher Shop Admin Report - {datetime.now().strftime('%Y-%m-%d')}"
        sent = send_email(recipient_email=admin_email, subject=subject, body=report)
        if sent:
            print(f"\nAdmin report emailed to {admin_email}")
        else:
            print(f"\nFailed to send admin report to {admin_email}")

    def _export_orders_csv(self):
        """Export butcher orders to CSV (same data/headers as the GUI export)."""
        import csv
        import os
        from education_system.post_18.university_system.infrastructure.database.db import get_db_connection

        default_path = f"butcher_orders_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        filepath = input(f"Output file path [{default_path}]: ").strip() or default_path

        headers = ['Order ID', 'Date/Time', 'Customer Name', 'Customer ID',
                   'Order Number', 'Amount', 'Payment Method', 'Payment Status']

        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT
                    bo.order_id,
                    bo.created_at,
                    bo.customer_name,
                    bo.customer_id,
                    bo.order_number,
                    bo.total_amount,
                    bo.payment_method,
                    bo.payment_status
                FROM orders bo
                WHERE bo.source_type = 'butcher' AND bo.payment_status != 'pending'
                ORDER BY bo.created_at DESC
                LIMIT 200
            ''').fetchall()

        count = 0
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for row in rows:
                values = list(row)
                if values[5] is not None:
                    try:
                        values[5] = f"{float(values[5]):.2f}"
                    except (ValueError, TypeError):
                        pass
                writer.writerow(values)
                count += 1

        print(f"\nExported {count} order(s) to {os.path.abspath(filepath)}")


def main():
    """Entry point for the Butcher Shop CLI."""
    cli = ButcherCLI()
    cli.run()


if __name__ == "__main__":
    main()
