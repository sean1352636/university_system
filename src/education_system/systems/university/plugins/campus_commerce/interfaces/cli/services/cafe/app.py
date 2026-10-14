from .context import *  # noqa: F401,F403
from education_system.systems.university.plugins.campus_commerce.domain.cafe.integrations.user_context import set_auth
from .commands.view_menu import view_menu_cli
from .commands.point_of_sale import point_of_sale_cli
from .commands.menu_management import menu_management_cli
from .commands.order_history import order_history_cli
from .commands.inventory import inventory_management_cli
from .commands.reports import reports_cli
from .commands.suppliers import supplier_management_cli
from .commands.reservations import reservations_cli
from .commands.loyalty import loyalty_points_cli
from .commands.staff_scheduling import staff_scheduling_cli

def display_cafe_menu() -> None:
    """Display the main menu for the cafe CLI."""
    global auth

    # Get auth from shared context if not set
    if not auth:
        auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text('cafe.not_logged_in', default='\nYou must be logged in to access the Cafe System.'))
        return

    # Initialize database if needed
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
            if not cursor.fetchone():
                conn.close()
                print("Cafe database not initialized. Initializing now...")
                if not init_cafe_db():
                    print("Failed to initialize cafe database.")
                    return
            else:
                conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if not init_cafe_db():
            print("Failed to initialize cafe database.")
            return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_menu_navigation('cafe_system_menu')

    while True:
        print("\n" + "=" * 60)
        print(f"              {get_text('cafe.title', default='UNIVERSITY CAFE SYSTEM')}")
        print("=" * 60)

        # Show quick summary
        summary = get_sales_summary("day")
        today_text = get_text('cafe.summary.today', default="Today's Sales")
        orders_text = get_text('cafe.summary.orders', default='orders')
        print(f"\n{today_text}: {summary['order_count']} {orders_text} | £{summary['total_sales']:.2f}")
        print("-" * 60)

        # Build menu based on permissions
        options = []
        option_num = 1

        # Point of Sale (available to all with permission)
        if auth.check_permission('update_takeaway_order_status') or auth.check_permission('manage_menu'):
            print(f"\n{option_num}. {get_text('cafe.menu.pos', default='New Order (Point of Sale)')}")
            options.append('pos')
            option_num += 1

        # View menu (available to all)
        print(f"{option_num}. {get_text('cafe.menu.view_menu', default='View Menu')}")
        options.append('view_menu')
        option_num += 1

        # Menu management
        if auth.check_permission('manage_menu') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.menu_mgmt', default='Menu Management')}")
            options.append('menu_mgmt')
            option_num += 1

        # Order history
        if auth.check_permission('view_all_takeaway_orders') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.orders', default='Order History')}")
            options.append('orders')
            option_num += 1

        # Inventory management
        if auth.check_permission('manage_inventory') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.inventory', default='Inventory Management')}")
            options.append('inventory')
            option_num += 1

        # Reports
        if auth.check_permission('generate_takeaway_reports') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.reports', default='Reports')}")
            options.append('reports')
            option_num += 1

        # Supplier management
        if auth.check_permission('manage_inventory') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.suppliers', default='Supplier Management')}")
            options.append('suppliers')
            option_num += 1

        # Reservations
        if auth.check_permission('update_takeaway_order_status') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.reservations', default='Reservations')}")
            options.append('reservations')
            option_num += 1

        # Loyalty points
        if auth.check_permission('update_takeaway_order_status') or auth.check_permission('manage_menu'):
            print(f"{option_num}. {get_text('cafe.menu.loyalty', default='Loyalty Points')}")
            options.append('loyalty')
            option_num += 1

        # Staff scheduling
        if auth.check_permission('manage_menu') or auth.check_permission('manage_inventory'):
            print(f"{option_num}. {get_text('cafe.menu.scheduling', default='Staff Scheduling')}")
            options.append('scheduling')
            option_num += 1

        # Language option
        print(f"{option_num}. {get_text('cafe.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('cafe.menu.return', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('cafe.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_num = int(choice)

            if choice_num > 0 and choice_num <= len(options):
                selected = options[choice_num - 1]

                if selected == 'pos':
                    point_of_sale_cli()
                elif selected == 'view_menu':
                    view_menu_cli()
                elif selected == 'menu_mgmt':
                    menu_management_cli()
                elif selected == 'orders':
                    order_history_cli()
                elif selected == 'inventory':
                    inventory_management_cli()
                elif selected == 'reports':
                    reports_cli()
                elif selected == 'suppliers':
                    supplier_management_cli()
                elif selected == 'reservations':
                    reservations_cli()
                elif selected == 'loyalty':
                    loyalty_points_cli()
                elif selected == 'scheduling':
                    staff_scheduling_cli()
                elif selected == 'language':
                    display_language_menu_option()

            elif choice_num == len(options) + 1:
                print(get_text('cafe.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('cafe.invalid_choice', default='Invalid choice. Please try again.'))

        except ValueError:
            if choice.lower() in ['q', 'quit', 'exit', 'back']:
                break
            print(get_text('cafe.invalid_input', default='Invalid input. Please enter a number.'))

