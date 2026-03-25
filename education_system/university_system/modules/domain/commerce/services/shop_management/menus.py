from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_menu_navigation
from education_system.university_system.modules.domain.commerce.services.shop_management import config
from education_system.university_system.modules.domain.commerce.services.shop_management.database import init_shop_db, setup_shop_permissions


@log_menu_navigation(description="Displaying shop main menu")
def display_shop_menu():
    """Display the main menu for the university shop"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.shopping import (browse_products, view_shopping_cart, checkout_process,
                           view_purchase_history, view_all_transactions)
    from education_system.university_system.modules.domain.commerce.services.shop_management.products import quick_add_product, bulk_update_prices

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to access the university shop.")
        return

    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if not cursor.fetchone():
            conn.close()
            print("Shop database not initialized. Initializing now...")
            if not init_shop_db():
                print("Failed to initialize shop database. Please contact system administrator.")
                return
        else:
            conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print("Trying to initialize shop database...")
        if not init_shop_db():
            print("Failed to initialize shop database. Please contact system administrator.")
            return

    while True:
        print("\nUniversity Shop Menu:")
        print("======================")

        # Show options based on permissions
        options = []
        option_num = 1

        # Customer options
        if config.auth.check_permission('view_products'):
            print(f"{option_num}. Browse Products")
            options.append('browse_products')
            option_num += 1

        if config.auth.check_permission('make_purchase'):
            print(f"{option_num}. View Shopping Cart")
            options.append('view_cart')
            option_num += 1

            print(f"{option_num}. Checkout")
            options.append('checkout')
            option_num += 1

        if config.auth.check_permission('view_own_purchase_history'):
            print(f"{option_num}. View Purchase History")
            options.append('purchase_history')
            option_num += 1

        # Admin options
        if config.auth.check_permission('manage_products'):
            print(f"{option_num}. Manage Products")
            options.append('manage_products')
            option_num += 1

        if config.auth.check_permission('manage_inventory'):
            print(f"{option_num}. Manage Inventory")
            options.append('manage_inventory')
            option_num += 1

        if config.auth.check_permission('view_all_transactions'):
            print(f"{option_num}. View All Transactions")
            options.append('all_transactions')
            option_num += 1

        if config.auth.check_permission('manage_discounts'):
            print(f"{option_num}. Manage Discounts")
            options.append('manage_discounts')
            option_num += 1

        if config.auth.check_permission('generate_sales_reports'):
            print(f"{option_num}. Generate Sales Reports")
            options.append('sales_reports')
            option_num += 1

        print(f"{option_num}. Return to Main Menu")

        choice = input("\nEnter your choice: ")

        try:
            choice_num = int(choice)

            if choice_num > 0 and choice_num <= len(options):
                selected_option = options[choice_num - 1]

                if selected_option == 'browse_products':
                    browse_products()
                elif selected_option == 'view_cart':
                    view_shopping_cart()
                elif selected_option == 'checkout':
                    checkout_process()
                elif selected_option == 'purchase_history':
                    view_purchase_history()
                elif selected_option == 'manage_products':
                    display_product_management_menu()
                elif selected_option == 'manage_inventory':
                    display_inventory_management_menu()
                elif selected_option == 'all_transactions':
                    view_all_transactions()
                elif selected_option == 'manage_discounts':
                    display_discount_management_menu()
                elif selected_option == 'sales_reports':
                    display_sales_reports_menu()
            elif choice_num == option_num:
                print("Returning to main menu...")
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

@log_menu_navigation(description="Displaying product management menu")
def display_product_management_menu():
    """Display the menu for product management"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.products import add_new_product, edit_product, toggle_product_status, view_all_products

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to manage products.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to manage products.")
        return

    while True:
        print("\nProduct Management Menu:")
        print("1. Add New Product")
        print("2. Edit Product")
        print("3. Deactivate/Activate Product")
        print("4. View All Products")
        print("5. Return to Shop Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            add_new_product()
        elif choice == '2':
            edit_product()
        elif choice == '3':
            toggle_product_status()
        elif choice == '4':
            view_all_products()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying inventory management menu")
def display_inventory_management_menu():
    """Display the menu for inventory management"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.inventory import (update_stock_levels, restock_products,
                            view_low_stock_products, adjust_restock_thresholds)

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to manage inventory.")
        return

    if not config.auth.check_permission('manage_inventory'):
        print("You don't have permission to manage inventory.")
        return

    while True:
        print("\nInventory Management Menu:")
        print("1. Update Stock Levels")
        print("2. Restock Products")
        print("3. View Low Stock Products")
        print("4. Adjust Restock Thresholds")
        print("5. Return to Shop Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            update_stock_levels()
        elif choice == '2':
            restock_products()
        elif choice == '3':
            view_low_stock_products()
        elif choice == '4':
            adjust_restock_thresholds()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying discount management menu")
def display_discount_management_menu():
    """Display the menu for discount management"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.discounts import (create_discount, edit_discount,
                            toggle_discount_status, view_all_discounts)

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to manage discounts.")
        return

    if not config.auth.check_permission('manage_discounts'):
        print("You don't have permission to manage discounts.")
        return

    while True:
        print("\nDiscount Management Menu:")
        print("1. Create New Discount")
        print("2. Edit Discount")
        print("3. Activate/Deactivate Discount")
        print("4. View All Discounts")
        print("5. Return to Shop Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            create_discount()
        elif choice == '2':
            edit_discount()
        elif choice == '3':
            toggle_discount_status()
        elif choice == '4':
            view_all_discounts()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying sales reports menu")
def display_sales_reports_menu():
    """Display the menu for sales reports"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.reports import (generate_daily_sales_report, generate_weekly_sales_report,
                          generate_monthly_sales_report, generate_product_sales_report,
                          generate_category_sales_report, export_sales_data)

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view sales reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    while True:
        print("\nSales Reports Menu:")
        print("1. Daily Sales Report")
        print("2. Weekly Sales Report")
        print("3. Monthly Sales Report")
        print("4. Product Sales Report")
        print("5. Category Sales Report")
        print("6. Export Sales Data")
        print("7. Return to Shop Menu")

        choice = input("Enter your choice (1-7): ").strip()

        if choice == '1':
            generate_daily_sales_report()
        elif choice == '2':
            generate_weekly_sales_report()
        elif choice == '3':
            generate_monthly_sales_report()
        elif choice == '4':
            generate_product_sales_report()
        elif choice == '5':
            generate_category_sales_report()
        elif choice == '6':
            export_sales_data()
        elif choice == '7':
            return
        else:
            print("Invalid choice. Please try again.")

# Main entry point - add to main.py
def display_main_menu_extended():
    """Extended display_menu function for the main module to include shop"""
    # Initialize all databases first
    if not init_all_databases():
        print("Failed to initialize databases. Exiting.")
        return

    # Initialize authentication system if not already done
    if config.auth is None:
        from education_system.university_system.infrastructure.auth import UserAuth
        config.auth = config.get_auth()
        if config.auth is None:
            config.auth = UserAuth()
        init_auth_for_modules()  # Initialize auth for other modules

    # Setup permissions for various modules
    setup_shop_permissions(config.auth)

    print("\nWelcome to the Student Record Management System!")

    # Main application loop
    while True:
        # Check if user is logged in
        if not config.auth or not config.auth.current_user:
            # User is not logged in, show authentication menu first
            print("\nPlease log in to access the system.")
            from education_system.university_system.infrastructure.auth import display_auth_menu
            config.auth = display_auth_menu()
            if config.auth is None:
                # Create a new auth object if none was returned
                from education_system.university_system.infrastructure.auth import UserAuth
                config.auth = config.get_auth()
                if config.auth is None:
                    config.auth = UserAuth()
            init_auth_for_modules()  # Reinitialize auth for other modules
            # Loop back to check if login was successful
            continue

        # User is now logged in, show main menu
        print(f"\nLogged in as: {config.auth.current_user['username']} ({config.auth.current_user['role']})")

        print("\nMain Menu:")
        print("==========")

        # Options based on permissions
        option_num = 1
        option_map = {}

        # ... (all existing menu options from the original function) ...

        # Show university shop option
        print(f"{option_num}. university shop")
        option_map[str(option_num)] = "university_shop"
        option_num += 1

        # ... (continue with other menu options) ...

        # Add logout option
        print(f"{option_num}. logout")
        option_map[str(option_num)] = "logout"
        option_num += 1

        # Add exit option
        print(f"{option_num}. exit")
        max_option = option_num

        choice = input("\nEnter your choice: ")

        if choice in option_map:
            option = option_map[choice]

            if option == "university_shop":
                display_shop_menu()
            # ... (handle other menu options) ...
            elif option == "logout":
                config.auth.logout()
                # Continue to loop back to login menu
        elif choice == str(max_option):
            # Exit
            if config.auth and config.auth.current_user:
                config.auth.logout()
            print("Thank you for using the Student Record Management System. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

# Integration function to add to main.py
def add_shop_system_to_main_menu(main_display_menu):
    """
    Adds the university shop system to the main menu options.
    This function should be called from main.py.

    Args:
        main_display_menu: The original display_menu function from main.py
    """
    # Initialize shop database
    init_shop_db()

    def extended_display_menu():
        """Extended version of display_menu that includes shop system"""
        # Initialize all databases first
        if not init_all_databases():
            print("Failed to initialize databases. Exiting.")
            return

        # Initialize authentication system if not already done
        if config.auth is None:
            from education_system.university_system.infrastructure.auth import UserAuth
            config.auth = config.get_auth()
            if config.auth is None:
                config.auth = UserAuth()
            init_auth_for_modules()  # Initialize auth for other modules

        # Setup permissions for various modules including shop
        setup_shop_permissions(config.auth)

        print("\nWelcome to the Student Record Management System!")

        # Main application loop
        while True:
            # Check if user is logged in
            if not config.auth or not config.auth.current_user:
                # User is not logged in, show authentication menu first
                print("\nPlease log in to access the system.")
                from education_system.university_system.infrastructure.auth import display_auth_menu
                config.auth = display_auth_menu()
                if config.auth is None:
                    # Create a new auth object if none was returned
                    from education_system.university_system.infrastructure.auth import UserAuth
                    config.auth = config.get_auth()
                    if config.auth is None:
                        config.auth = UserAuth()
                init_auth_for_modules()  # Reinitialize auth for other modules
                # Loop back to check if login was successful
                continue

            # User is now logged in, show main menu
            print(f"\nLogged in as: {config.auth.current_user['username']} ({config.auth.current_user['role']})")

            print("\nMain Menu:")
            print("==========")

            # Options based on permissions
            option_num = 1
            option_map = {}

            # Show standard options
            # ... (all existing menu options from original function) ...

            # Show university shop option - available to all authenticated users
            print(f"{option_num}. University Shop")
            option_map[str(option_num)] = "university_shop"
            option_num += 1

            # ... (continue with other menu options) ...

            # Add logout option
            print(f"{option_num}. Logout")
            option_map[str(option_num)] = "logout"
            option_num += 1

            # Add exit option
            print(f"{option_num}. Exit")
            max_option = option_num

            choice = input("\nEnter your choice: ")

            if choice in option_map:
                option = option_map[choice]

                if option == "university_shop":
                    display_shop_menu()
                # ... (handle other menu options) ...
                elif option == "logout":
                    config.auth.logout()
                    # Continue to loop back to login menu
            elif choice == str(max_option):
                # Exit
                if config.auth and config.auth.current_user:
                    config.auth.logout()
                print("Thank you for using the Student Record Management System. Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")

    # Return the extended menu function
    return extended_display_menu


def setup_shop_system():
    """Complete setup function for the shop system"""
    from education_system.university_system.modules.domain.commerce.services.shop_management.discounts import cleanup_expired_discounts

    print("Setting up University Shop System...")

    # Initialize databases
    if not init_all_databases():
        print("❌ Failed to initialize databases")
        return False

    # Initialize authentication
    if not config.auth:
        from education_system.university_system.infrastructure.auth import UserAuth
        config.auth = config.get_auth()
        if config.auth is None:
            config.auth = UserAuth()

    # Setup permissions
    if not setup_shop_permissions(config.auth):
        print("❌ Failed to setup shop permissions")
        return False

    # Create sample users if needed
    create_sample_users()

    # Clean up expired discounts
    cleanup_expired_discounts()

    print("✅ Shop system setup complete!")
    return True


def integrate_shop_with_main():
    """
    Main integration function to be called from main.py
    This sets up everything needed for the shop system
    """
    from education_system.university_system.modules.domain.commerce.services.shop_management.utils import test_shop_system

    print("🏪 Initializing University Shop System...")

    # Setup the complete system
    if not setup_shop_system():
        print("❌ Failed to setup shop system")
        return False

    # Test the system
    if not test_shop_system():
        print("❌ Shop system tests failed")
        return False

    print("✅ University Shop System ready!")
    return True
