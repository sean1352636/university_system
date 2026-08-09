"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def butcher_menu():
    """Main butcher shop menu"""
    try:
        # Initialize database
        init_butcher_db()
    except Exception as e:
        logger.error(f"Failed to initialize butcher database: {e}")
        print(f"❌ Failed to initialize butcher system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Butcher Shop")
        input("\nPress Enter to continue...")
        return

    is_staff = user.get('role') in ['admin', 'staff']

    while True:
        try:
            print_header("UNIVERSITY BUTCHER SHOP")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n🥩 PRODUCTS:")
            print("1. Browse Products by Category")
            print("2. View Product Details")
            print("3. Search Products")

            print("\n🛒 ORDERS:")
            print("4. Place Order")
            print("5. View My Orders")
            print("6. View Order Receipt")
            print("7. Cancel Order")

            if is_staff:
                print("\n📦 INVENTORY (Staff):")
                print("8. View Inventory Status")
                print("9. Adjust Inventory")
                print("10. Low Stock Alerts")
                print("11. Manage Expiry Dates")

                print("\n📊 REPORTS (Staff):")
                print("12. Sales Reports")
                print("13. Inventory Valuation")
                print("14. Popular Products Analysis")
                print("15. Customer Purchase History")

                print("\n🔧 ADMIN:")
                print("16. Add Product")
                print("17. Update Product")
                print("18. View All Orders")
                print("19. Update Order Status")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                browse_products_by_category()
            elif choice == "2":
                view_product_details()
            elif choice == "3":
                search_products()
            elif choice == "4":
                place_order()
            elif choice == "5":
                view_my_orders()
            elif choice == "6":
                view_order_receipt()
            elif choice == "7":
                cancel_order()
            elif choice == "8" and is_staff:
                view_inventory()
            elif choice == "9" and is_staff:
                adjust_inventory()
            elif choice == "10" and is_staff:
                view_low_stock_alerts()
            elif choice == "11" and is_staff:
                manage_expiry_dates()
            elif choice == "12" and is_staff:
                sales_reports()
            elif choice == "13" and is_staff:
                inventory_valuation_report()
            elif choice == "14" and is_staff:
                popular_products_analysis()
            elif choice == "15" and is_staff:
                customer_purchase_history()
            elif choice == "16" and is_staff:
                add_product()
            elif choice == "17" and is_staff:
                update_product()
            elif choice == "18" and is_staff:
                view_all_orders()
            elif choice == "19" and is_staff:
                update_order_status()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in butcher menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")
