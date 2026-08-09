from ..context import *  # noqa: F401,F403

def reports_cli() -> None:
    """View reports."""
    while True:
        print("\n--- Cafe Reports ---")
        print("1. Daily Sales Report")
        print("2. Weekly Sales Report")
        print("3. Monthly Sales Report")
        print("4. Popular Items")
        print("5. Low Stock Alert")
        print("6. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            summary = get_sales_summary("day")
            print(f"\n{'=' * 50}")
            print("DAILY SALES REPORT")
            print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            print("\nSales by Payment Method:")
            for method, count, amount in summary['payment_breakdown']:
                print(f"  {method}: {count} orders, £{amount:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            summary = get_sales_summary("week")
            print(f"\n{'=' * 50}")
            print("WEEKLY SALES REPORT")
            print(f"Week ending: {datetime.now().strftime('%Y-%m-%d')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            if summary['order_count'] > 0:
                print(f"Average per order: £{summary['total_sales']/summary['order_count']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            summary = get_sales_summary("month")
            print(f"\n{'=' * 50}")
            print("MONTHLY SALES REPORT")
            print(f"Month: {datetime.now().strftime('%B %Y')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '4':
            items = get_popular_items(20)
            print(f"\n{'=' * 60}")
            print("TOP 20 MOST POPULAR ITEMS")
            print(f"{'=' * 60}")
            if items:
                for i, (name, qty, sales) in enumerate(items, 1):
                    print(f"{i:>2}. {name}: {qty} units sold, £{sales:.2f} revenue")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = get_low_stock_items(20)
            print(f"\n{'=' * 50}")
            print("LOW STOCK ALERT")
            print(f"{'=' * 50}")
            if items:
                for name, cat, stock in items:
                    status = "OUT OF STOCK" if stock == 0 else "LOW STOCK"
                    print(f"[{status}] {name} ({cat}): {stock} units")
            else:
                print("All items have adequate stock levels.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            break

