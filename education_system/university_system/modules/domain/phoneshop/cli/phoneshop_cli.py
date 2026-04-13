"""
Phone Shop CLI Interface

Command-line interface for phone shop operations including
product management, orders, payments, refunds, and reports.
"""

from education_system.university_system.modules.domain.phoneshop.services.phoneshop_core import (
    ORDER_STATUSES,
    PHONE_CATEGORIES,
    OrderManager,
    ProductManager,
    ReportManager,
    TransactionManager,
    init_phoneshop_db,
)


class PhoneShopCLI:
    """CLI interface for Phone Shop operations."""

    def __init__(self):
        """Initialize the Phone Shop CLI and ensure DB tables exist."""
        try:
            init_phoneshop_db()
        except Exception as e:
            print(f"Warning: Could not initialize phone shop database: {e}")

    def display_menu(self):
        """Display the main phone shop menu and handle user input."""
        while True:
            print("\n" + "=" * 60)
            print(" " * 20 + "PHONE SHOP SYSTEM")
            print("=" * 60)

            print("\n[Products]")
            print("  1. View All Products")
            print("  2. View Products by Category")
            print("  3. Search Products")
            print("  4. View Product Details")
            print("  5. Add Product")
            print("  6. Update Product")
            print("  7. Update Stock")
            print("  8. View Low Stock Products")

            print("\n[Orders]")
            print("  9. Create Order")
            print(" 10. View Order Details")
            print(" 11. View Orders by Status")
            print(" 12. View Customer Orders")
            print(" 13. Update Order Status")
            print(" 14. Cancel Order")

            print("\n[Payments]")
            print(" 15. Record Payment")
            print(" 16. Process Refund")

            print("\n[Reports]")
            print(" 17. Sales Summary")
            print(" 18. Inventory Summary")
            print(" 19. Top Selling Products")
            print(" 20. Full Admin Report")

            print("\n  0. Back to Main Menu")
            print("=" * 60)

            choice = input("\nEnter your choice: ").strip()

            try:
                if choice == "0":
                    break
                elif choice == "1":
                    self._view_all_products()
                elif choice == "2":
                    self._view_by_category()
                elif choice == "3":
                    self._search_products()
                elif choice == "4":
                    self._view_product_details()
                elif choice == "5":
                    self._add_product()
                elif choice == "6":
                    self._update_product()
                elif choice == "7":
                    self._update_stock()
                elif choice == "8":
                    self._view_low_stock()
                elif choice == "9":
                    self._create_order()
                elif choice == "10":
                    self._view_order()
                elif choice == "11":
                    self._view_orders_by_status()
                elif choice == "12":
                    self._view_customer_orders()
                elif choice == "13":
                    self._update_order_status()
                elif choice == "14":
                    self._cancel_order()
                elif choice == "15":
                    self._record_payment()
                elif choice == "16":
                    self._process_refund()
                elif choice == "17":
                    self._sales_summary()
                elif choice == "18":
                    self._inventory_summary()
                elif choice == "19":
                    self._top_selling()
                elif choice == "20":
                    self._admin_report()
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"\nError: {e}")

    # ── Products ────────────────────────────────────────────

    def _view_all_products(self):
        """View all active products."""
        products = ProductManager.get_all_products()
        if not products:
            print("\nNo products found.")
            return
        self._print_product_list(products)

    def _view_by_category(self):
        """View products by category."""
        print("\nCategories:", ", ".join(PHONE_CATEGORIES))
        category = input("Enter category: ").strip()
        products = ProductManager.get_products_by_category(category)
        if not products:
            print(f"\nNo products found in category '{category}'.")
            return
        self._print_product_list(products)

    def _search_products(self):
        """Search products by name, brand, model, or SKU."""
        query = input("Search query: ").strip()
        if not query:
            print("Search query cannot be empty.")
            return
        products = ProductManager.search_products(query)
        if not products:
            print(f"\nNo products matching '{query}'.")
            return
        self._print_product_list(products)

    def _view_product_details(self):
        """View full details for a single product."""
        product_id = int(input("Product ID: ").strip())
        product = ProductManager.get_product(product_id)
        if not product:
            print("Product not found.")
            return
        print(f"\n--- Product #{product['product_id']} ---")
        print(f"  SKU:          {product['sku']}")
        print(f"  Name:         {product['name']}")
        print(f"  Brand:        {product.get('brand') or '-'}")
        print(f"  Model:        {product.get('model') or '-'}")
        print(f"  Category:     {product['category']}")
        print(f"  Price:        £{product['price']:.2f}")
        print(f"  Cost Price:   £{(product.get('cost_price') or 0):.2f}")
        print(f"  Stock:        {product['stock_quantity']}")
        print(f"  Min Stock:    {product['min_stock_level']}")
        print(f"  Warranty:     {product['warranty_months']} months")
        if product.get("description"):
            print(f"  Description:  {product['description']}")

    def _print_product_list(self, products):
        """Print a list of products in tabular format."""
        print(f"\n{'ID':<5} {'SKU':<15} {'Name':<25} {'Category':<14} {'Price':<9} {'Stock':<6}")
        print("-" * 74)
        for p in products:
            print(
                f"{p['product_id']:<5} {p['sku']:<15} {p['name']:<25} "
                f"{p['category']:<14} £{p['price']:<8.2f} {p['stock_quantity']:<6}"
            )

    def _add_product(self):
        """Add a new product."""
        sku = input("SKU: ").strip()
        name = input("Product name: ").strip()
        if not sku or not name:
            print("SKU and name are required.")
            return
        print("Categories:", ", ".join(PHONE_CATEGORIES))
        category = input("Category: ").strip()
        price = float(input("Price (£): ").strip())

        brand = input("Brand (optional): ").strip() or None
        model = input("Model (optional): ").strip() or None
        description = input("Description (optional): ").strip() or None
        cost_price_input = input("Cost price (optional): ").strip()
        cost_price = float(cost_price_input) if cost_price_input else None
        stock_input = input("Initial stock quantity (default 0): ").strip()
        stock = int(stock_input) if stock_input else 0
        warranty_input = input("Warranty months (default 12): ").strip()
        warranty = int(warranty_input) if warranty_input else 12

        product_id = ProductManager.add_product(
            sku=sku, name=name, category=category, price=price,
            brand=brand, model=model, description=description,
            cost_price=cost_price, stock_quantity=stock,
            warranty_months=warranty,
        )
        if product_id:
            print(f"\nProduct added successfully (ID: {product_id}).")
        else:
            print("\nFailed to add product. SKU may already exist.")

    def _update_product(self):
        """Update an existing product."""
        product_id = int(input("Product ID to update: ").strip())
        product = ProductManager.get_product(product_id)
        if not product:
            print("Product not found.")
            return
        print(f"Current: {product['name']} | {product['category']} | £{product['price']:.2f}")

        updates = {}
        name = input(f"New name (Enter to keep): ").strip()
        if name:
            updates["name"] = name
        price = input(f"New price (Enter to keep): ").strip()
        if price:
            updates["price"] = float(price)
        description = input("New description (Enter to keep): ").strip()
        if description:
            updates["description"] = description

        if not updates:
            print("No changes made.")
            return
        if ProductManager.update_product(product_id, **updates):
            print("Product updated successfully.")
        else:
            print("Failed to update product.")

    def _update_stock(self):
        """Update product stock level."""
        product_id = int(input("Product ID: ").strip())
        change = int(input("Stock change (positive to add, negative to subtract): ").strip())
        if ProductManager.update_stock(product_id, change):
            print("Stock updated successfully.")
        else:
            print("Failed to update stock.")

    def _view_low_stock(self):
        """View products with stock at or below minimum level."""
        products = ProductManager.get_low_stock_products()
        if not products:
            print("\nNo low-stock products.")
            return
        print("\nLow Stock Products:")
        self._print_product_list(products)

    # ── Orders ──────────────────────────────────────────────

    def _create_order(self):
        """Create a new order."""
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        if not customer_id or not customer_name:
            print("Customer ID and name are required.")
            return

        items = []
        while True:
            print("\nAdd order item (or press Enter with empty Product ID to finish):")
            pid_input = input("  Product ID: ").strip()
            if not pid_input:
                break
            product = ProductManager.get_product(int(pid_input))
            if not product:
                print("  Product not found. Try again.")
                continue
            print(f"  Product: {product['name']} (£{product['price']:.2f}, stock: {product['stock_quantity']})")
            qty = int(input("  Quantity: ").strip())
            serial = input("  Serial number (optional): ").strip() or None
            items.append({
                "product_id": product["product_id"],
                "product_name": product["name"],
                "unit_price": product["price"],
                "quantity": qty,
                "serial_number": serial,
            })

        if not items:
            print("At least one item is required.")
            return

        customer_email = input("Customer email (optional): ").strip() or None
        customer_phone = input("Customer phone (optional): ").strip() or None
        shipping = input("Shipping address (optional): ").strip() or None
        payment = input("Payment method (optional): ").strip() or None

        order_id = OrderManager.create_order(
            customer_id=customer_id, customer_name=customer_name, items=items,
            customer_email=customer_email, customer_phone=customer_phone,
            shipping_address=shipping, payment_method=payment,
        )
        if order_id:
            print(f"\nOrder created successfully (ID: {order_id}).")
        else:
            print("\nFailed to create order.")

    def _view_order(self):
        """View order details."""
        order_id = int(input("Order ID: ").strip())
        order = OrderManager.get_order(order_id)
        if not order:
            print("Order not found.")
            return
        print(f"\n--- Order #{order['order_id']} ---")
        print(f"  Order Number:  {order['order_number']}")
        print(f"  Customer:      {order['customer_name']} ({order['customer_id']})")
        print(f"  Status:        {order['order_status']}")
        print(f"  Payment:       {order['payment_status']}")
        print(f"  Subtotal:      £{order['subtotal']:.2f}")
        print(f"  Tax:           £{order['tax_amount']:.2f}")
        print(f"  Shipping:      £{order['shipping_fee']:.2f}")
        print(f"  Discount:      £{order['discount_amount']:.2f}")
        print(f"  Total:         £{order['total_amount']:.2f}")
        if order.get("items"):
            print("  Items:")
            for item in order["items"]:
                print(f"    - {item['item_name']} x{item['quantity']} @ £{item['unit_price']:.2f} = £{item['subtotal']:.2f}")

    def _view_orders_by_status(self):
        """View orders filtered by status."""
        print("Statuses:", ", ".join(ORDER_STATUSES))
        status = input("Enter status: ").strip()
        orders = OrderManager.get_orders_by_status(status)
        if not orders:
            print(f"\nNo orders with status '{status}'.")
            return
        self._print_order_list(orders)

    def _view_customer_orders(self):
        """View all orders for a customer."""
        customer_id = input("Customer ID: ").strip()
        orders = OrderManager.get_customer_orders(customer_id)
        if not orders:
            print(f"\nNo orders found for customer '{customer_id}'.")
            return
        self._print_order_list(orders)

    def _print_order_list(self, orders):
        """Print a list of orders in tabular format."""
        print(f"\n{'ID':<5} {'Order #':<22} {'Customer':<18} {'Status':<12} {'Payment':<12} {'Total':<10}")
        print("-" * 79)
        for o in orders:
            print(
                f"{o['order_id']:<5} {o['order_number']:<22} {o['customer_name']:<18} "
                f"{o['order_status']:<12} {o['payment_status']:<12} £{o['total_amount']:.2f}"
            )

    def _update_order_status(self):
        """Update the status of an order."""
        order_id = int(input("Order ID: ").strip())
        print("Statuses:", ", ".join(ORDER_STATUSES))
        status = input("New status: ").strip()
        if OrderManager.update_order_status(order_id, status):
            print("Order status updated successfully.")
        else:
            print("Failed to update order status.")

    def _cancel_order(self):
        """Cancel an order and restore stock."""
        order_id = int(input("Order ID to cancel: ").strip())
        reason = input("Cancellation reason (optional): ").strip() or None
        if OrderManager.cancel_order(order_id, reason):
            print("Order cancelled and stock restored successfully.")
        else:
            print("Failed to cancel order.")

    # ── Payments ────────────────────────────────────────────

    def _record_payment(self):
        """Record a payment for an order."""
        order_id = int(input("Order ID: ").strip())
        order = OrderManager.get_order(order_id)
        if not order:
            print("Order not found.")
            return
        print(f"Order total: £{order['total_amount']:.2f}")
        amount = float(input("Payment amount (£): ").strip())
        payment_method = input("Payment method (card/cash/contactless/bank_transfer): ").strip()
        processed_by = input("Processed by (staff ID, optional): ").strip() or None

        txn_id = TransactionManager.record_payment(
            order_id=order_id, customer_id=order["customer_id"],
            amount=amount, payment_method=payment_method,
            processed_by=processed_by,
        )
        if txn_id:
            print(f"\nPayment recorded successfully (Transaction ID: {txn_id}).")
        else:
            print("\nFailed to record payment.")

    def _process_refund(self):
        """Process a refund for an order."""
        order_id = int(input("Order ID: ").strip())
        amount = float(input("Refund amount (£): ").strip())
        reason = input("Refund reason (optional): ").strip() or None
        processed_by = input("Processed by (staff ID, optional): ").strip() or None

        txn_id = TransactionManager.process_refund(
            order_id=order_id, amount=amount, reason=reason,
            processed_by=processed_by,
        )
        if txn_id:
            print(f"\nRefund processed successfully (Transaction ID: {txn_id}).")
        else:
            print("\nFailed to process refund.")

    # ── Reports ─────────────────────────────────────────────

    def _sales_summary(self):
        """Display sales summary."""
        summary = ReportManager.get_sales_summary()
        print("\n--- Sales Summary ---")
        print(f"  Total Orders:      {summary['total_orders']}")
        print(f"  Total Revenue:     £{summary['total_revenue']:.2f}")
        print(f"  Avg Order Value:   £{summary['avg_order_value']:.2f}")
        print(f"  Pending Orders:    {summary['pending_orders']}")
        print(f"  Completed Orders:  {summary['completed_orders']}")

    def _inventory_summary(self):
        """Display inventory summary."""
        summary = ReportManager.get_inventory_summary()
        print("\n--- Inventory Summary ---")
        print(f"  Total Products:    {summary['total_products']}")
        print(f"  Total Stock:       {summary['total_stock']}")
        print(f"  Inventory Value:   £{summary['total_value']:.2f}")
        print(f"  Low Stock Items:   {summary['low_stock_count']}")

    def _top_selling(self):
        """Display top selling products."""
        limit_input = input("Number of top products to show (default 10): ").strip()
        limit = int(limit_input) if limit_input else 10
        products = ReportManager.get_top_selling_products(limit)
        if not products:
            print("\nNo sales data available.")
            return
        print(f"\n--- Top {limit} Selling Products ---")
        for i, p in enumerate(products, 1):
            sold = p.get("total_sold", 0)
            revenue = p.get("total_revenue", 0)
            print(f"  {i}. {p['name']} - {sold} units sold (£{revenue:.2f})")

    def _admin_report(self):
        """Generate and display the full admin report."""
        report = ReportManager.generate_admin_report()
        print(report)


def main():
    """Entry point for the Phone Shop CLI."""
    cli = PhoneShopCLI()
    cli.display_menu()


if __name__ == "__main__":
    main()
