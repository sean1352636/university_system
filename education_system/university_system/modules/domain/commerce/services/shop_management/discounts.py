from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_create, log_update, log_read
from education_system.university_system.modules.domain.commerce.services.shop_management import config


@log_create(module="shop", description="Creating new discount")
def create_discount():
    """Create a new discount in the shop system"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to create discounts.")
        return

    if not config.auth.check_permission('manage_discounts'):
        print("You don't have permission to create discounts.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCreate New Discount:")

        # Generate discount ID
        cursor.execute("SELECT MAX(SUBSTR(discount_id, 2)) FROM shop_discounts WHERE discount_id LIKE 'D%'")
        result = cursor.fetchone()

        try:
            if result[0]:
                next_id = int(result[0]) + 1
            else:
                next_id = 1
            discount_id = f"D{next_id:03d}"
        except (ValueError, TypeError):
            discount_id = f"D{int(time.time())}"

        print(f"Generated Discount ID: {discount_id}")

        # Get discount details
        name = None
        while not name:
            name = input("Discount Name: ").strip()
            if not name:
                print("Discount name cannot be empty.")

        description = input("Description: ").strip()

        # Get discount type
        print("\nDiscount Types:")
        print("1. Percentage (%) off")
        print("2. Fixed Amount (£) off")

        discount_type = None
        while not discount_type:
            type_choice = input("Select discount type (1-2): ").strip()
            if type_choice == '1':
                discount_type = 'percentage'
            elif type_choice == '2':
                discount_type = 'fixed'
            else:
                print("Invalid choice. Please select 1 or 2.")

        # Get discount value
        discount_value = None
        while discount_value is None:
            try:
                value_input = input("Discount Value: ").strip()
                discount_value = float(value_input)

                if discount_value <= 0:
                    print("Discount value must be greater than 0.")
                    discount_value = None
                    continue

                if discount_type == 'percentage' and discount_value > 100:
                    print("Percentage discount cannot exceed 100%.")
                    discount_value = None
            except ValueError:
                print("Invalid value. Please enter a number.")

        # Get date range (optional)
        start_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nStart Date [default: current time ({start_date})]: ")
        custom_start = input("Enter custom start date (YYYY-MM-DD) or press Enter for default: ").strip()
        if custom_start:
            try:
                # Validate date format
                datetime.strptime(custom_start, '%Y-%m-%d')
                start_date = f"{custom_start} 00:00:00"
            except ValueError:
                print(f"Invalid date format. Using default ({start_date}).")

        end_date = None
        has_end_date = input("Set an end date? (y/n): ").strip().lower()
        if has_end_date == 'y':
            while True:
                end_date_input = input("End Date (YYYY-MM-DD): ").strip()
                try:
                    # Validate date format
                    end_date_obj = datetime.strptime(end_date_input, '%Y-%m-%d')
                    start_date_obj = datetime.strptime(start_date.split()[0], '%Y-%m-%d')

                    if end_date_obj <= start_date_obj:
                        print("End date must be after start date.")
                        continue

                    end_date = f"{end_date_input} 23:59:59"
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")

        # Get applicable products
        print("\nApplicable Products:")
        print("1. All products")
        print("2. Specific category")
        print("3. Custom product list")

        applicable_products = 'all'
        applicable_choice = input("Select option (1-3): ").strip()

        if applicable_choice == '2':
            # Get categories
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' ORDER BY category")
            categories = cursor.fetchall()

            if not categories:
                print("No categories found. Using 'all' as default.")
            else:
                print("\nAvailable Categories:")
                for i, category in enumerate(categories):
                    print(f"{i+1}. {category[0]}")

                try:
                    cat_choice = int(input("Select category number: ").strip())
                    if cat_choice < 1 or cat_choice > len(categories):
                        print("Invalid selection. Using 'all' as default.")
                    else:
                        applicable_products = categories[cat_choice-1][0]
                except ValueError:
                    print("Invalid input. Using 'all' as default.")

        elif applicable_choice == '3':
            # Custom product list
            product_list = []

            cursor.execute("SELECT source_product_id as product_id, name FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY name")
            products = cursor.fetchall()

            if not products:
                print("No active products found. Using 'all' as default.")
            else:
                print("\nSelect products (enter product IDs, one per line, blank line to finish):")
                print("\nAvailable Products:")
                for i, product in enumerate(products):
                    print(f"{product[0]}: {product[1]}")

                while True:
                    product_id = input("Enter Product ID (or blank to finish): ").strip().upper()
                    if not product_id:
                        break

                    # Verify product exists
                    cursor.execute("SELECT 1 FROM products WHERE source_type = 'shop' AND source_product_id = ? AND is_active = 1", [product_id])
                    if cursor.fetchone():
                        if product_id not in product_list:
                            product_list.append(product_id)
                            print(f"Added: {product_id}")
                        else:
                            print(f"Product {product_id} already in list.")
                    else:
                        print(f"Product {product_id} not found or not active.")

                if product_list:
                    applicable_products = ','.join(product_list)
                else:
                    print("No products selected. Using 'all' as default.")

        # Get minimum purchase amount
        min_purchase = 0.0
        min_input = input("\nMinimum Purchase Amount (£) [default: 0]: ").strip()
        if min_input:
            try:
                min_purchase = float(min_input)
                if min_purchase < 0:
                    print("Minimum purchase cannot be negative. Using 0.")
                    min_purchase = 0.0
            except ValueError:
                print("Invalid amount. Using 0.")

        # Current datetime for created_at
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert discount
        cursor.execute(
            '''
            INSERT INTO shop_discounts
            (discount_id, name, description, discount_type, discount_value,
             start_date, end_date, is_active, applicable_products, min_purchase_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [discount_id, name, description, discount_type, discount_value,
             start_date, end_date, 1, applicable_products, min_purchase, now]
        )

        conn.commit()

        print(f"\nDiscount {discount_id} created successfully!")
        print(f"Name: {name}")
        print(f"Type: {discount_type.capitalize()}")
        print(f"Value: {'£' if discount_type == 'fixed' else ''}{discount_value}{'%' if discount_type == 'percentage' else ''}")
        print(f"Start Date: {start_date}")
        if end_date:
            print(f"End Date: {end_date}")
        print(f"Applicable Products: {applicable_products}")
        if min_purchase > 0:
            print(f"Minimum Purchase: £{min_purchase:.2f}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error creating discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error creating discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_update(module="shop", description="Editing discount")
def edit_discount():
    """Edit an existing discount"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to edit discounts.")
        return

    if not config.auth.check_permission('manage_discounts'):
        print("You don't have permission to edit discounts.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get discount list
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, end_date, name
            '''
        )

        discounts = cursor.fetchall()

        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return

        # Display discount list
        print("\nDiscount List:")
        print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Active'}")
        print("-" * 100)

        for discount in discounts:
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            active_status = "Yes" if discount['is_active'] else "No"

            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {active_status}")

        # Get discount to edit
        discount_id = input("\nEnter discount ID to edit: ").strip().upper()

        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )

        discount = cursor.fetchone()

        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return

        # Display current discount details
        print(f"\nEditing Discount: {discount['discount_id']} - {discount['name']}")
        print("Current details:")
        print(f"Name: {discount['name']}")
        print(f"Description: {discount['description']}")
        print(f"Type: {discount['discount_type']}")
        value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
        print(f"Value: {value_display}")
        print(f"Start Date: {discount['start_date']}")
        print(f"End Date: {discount['end_date'] if discount['end_date'] else 'Never'}")
        print(f"Applicable Products: {discount['applicable_products']}")
        print(f"Minimum Purchase: £{discount['min_purchase_amount']:.2f}")
        print(f"Active: {'Yes' if discount['is_active'] else 'No'}")

        # Get updated details
        print("\nEnter new details (leave blank to keep current value):")

        name = input(f"Name [{discount['name']}]: ").strip()
        if not name:
            name = discount['name']

        description = input(f"Description [{discount['description']}]: ").strip()
        if not description:
            description = discount['description']

        # Type and value need special handling to maintain compatibility
        discount_type = discount['discount_type']
        discount_value = discount['discount_value']

        update_type = input(f"Update discount type/value? (currently {discount_type}, {value_display}) (y/n): ").strip().lower()
        if update_type == 'y':
            print("\nDiscount Types:")
            print("1. Percentage (%) off")
            print("2. Fixed Amount (£) off")

            type_choice = input(f"Select discount type [current: {1 if discount_type == 'percentage' else 2}]: ").strip()
            if type_choice == '1':
                discount_type = 'percentage'
            elif type_choice == '2':
                discount_type = 'fixed'

            value_input = input(f"Discount Value [current: {discount_value}]: ").strip()
            if value_input:
                try:
                    discount_value = float(value_input)
                    if discount_value <= 0:
                        print("Discount value must be greater than 0. Keeping current value.")
                        discount_value = discount['discount_value']
                    elif discount_type == 'percentage' and discount_value > 100:
                        print("Percentage discount cannot exceed 100%. Setting to 100.")
                        discount_value = 100.0
                except ValueError:
                    print("Invalid value. Keeping current value.")
                    discount_value = discount['discount_value']

        # Date range
        update_dates = input("Update date range? (y/n): ").strip().lower()
        start_date = discount['start_date']
        end_date = discount['end_date']

        if update_dates == 'y':
            start_input = input(f"Start Date [{start_date}] (YYYY-MM-DD): ").strip()
            if start_input:
                try:
                    # Validate date format
                    datetime.strptime(start_input, '%Y-%m-%d')
                    start_date = f"{start_input} 00:00:00"
                except ValueError:
                    print(f"Invalid date format. Keeping current value.")

            has_end_date = input(f"Set an end date? (currently {'Yes' if end_date else 'No'}) (y/n): ").strip().lower()
            if has_end_date == 'y':
                end_input = input("End Date (YYYY-MM-DD): ").strip()
                try:
                    # Validate date format
                    end_date_obj = datetime.strptime(end_input, '%Y-%m-%d')
                    start_date_obj = datetime.strptime(start_date.split()[0], '%Y-%m-%d')

                    if end_date_obj <= start_date_obj:
                        print("End date must be after start date. Keeping current value.")
                    else:
                        end_date = f"{end_input} 23:59:59"
                except ValueError:
                    print("Invalid date format. Keeping current value.")
            else:
                end_date = None

        # Applicable products
        applicable_products = discount['applicable_products']
        update_applicable = input("Update applicable products? (y/n): ").strip().lower()

        if update_applicable == 'y':
            print("\nApplicable Products:")
            print("1. All products")
            print("2. Specific category")
            print("3. Custom product list")

            applicable_choice = input("Select option (1-3): ").strip()

            if applicable_choice == '1':
                applicable_products = 'all'
            elif applicable_choice == '2':
                # Get categories
                cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'shop' ORDER BY category")
                categories = cursor.fetchall()

                if not categories:
                    print("No categories found. Using 'all' as default.")
                    applicable_products = 'all'
                else:
                    print("\nAvailable Categories:")
                    for i, category in enumerate(categories):
                        print(f"{i+1}. {category[0]}")

                    try:
                        cat_choice = int(input("Select category number: ").strip())
                        if cat_choice < 1 or cat_choice > len(categories):
                            print("Invalid selection. Keeping current value.")
                        else:
                            applicable_products = categories[cat_choice-1][0]
                    except ValueError:
                        print("Invalid input. Keeping current value.")

            elif applicable_choice == '3':
                # Custom product list
                product_list = []

                cursor.execute("SELECT source_product_id as product_id, name FROM products WHERE source_type = 'shop' AND is_active = 1 ORDER BY name")
                products = cursor.fetchall()

                if not products:
                    print("No active products found. Using 'all' as default.")
                    applicable_products = 'all'
                else:
                    print("\nSelect products (enter product IDs, one per line, blank line to finish):")
                    print("\nAvailable Products:")
                    for product in products:
                        print(f"{product[0]}: {product[1]}")

                    while True:
                        product_id = input("Enter Product ID (or blank to finish): ").strip().upper()
                        if not product_id:
                            break

                        # Verify product exists
                        cursor.execute("SELECT 1 FROM products WHERE source_type = 'shop' AND source_product_id = ? AND is_active = 1", [product_id])
                        if cursor.fetchone():
                            if product_id not in product_list:
                                product_list.append(product_id)
                                print(f"Added: {product_id}")
                            else:
                                print(f"Product {product_id} already in list.")
                        else:
                            print(f"Product {product_id} not found or not active.")

                    if product_list:
                        applicable_products = ','.join(product_list)
                    else:
                        print("No products selected. Keeping current value.")

        # Minimum purchase
        min_purchase = discount['min_purchase_amount']
        min_input = input(f"Minimum Purchase Amount (£) [current: {min_purchase:.2f}]: ").strip()
        if min_input:
            try:
                min_purchase = float(min_input)
                if min_purchase < 0:
                    print("Minimum purchase cannot be negative. Using 0.")
                    min_purchase = 0.0
            except ValueError:
                print("Invalid amount. Keeping current value.")

        # Update discount
        cursor.execute(
            '''
            UPDATE shop_discounts
            SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                start_date = ?, end_date = ?, applicable_products = ?, min_purchase_amount = ?
            WHERE discount_id = ?
            ''',
            [name, description, discount_type, discount_value, start_date, end_date,
             applicable_products, min_purchase, discount_id]
        )

        conn.commit()

        print(f"\nDiscount {discount_id} updated successfully!")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error editing discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error editing discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_update(module="shop", description="Toggling discount status")
def toggle_discount_status():
    """Activate or deactivate a discount"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to change discount status.")
        return

    if not config.auth.check_permission('manage_discounts'):
        print("You don't have permission to change discount status.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get discount list
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, name
            '''
        )

        discounts = cursor.fetchall()

        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return

        # Display discount list
        print("\nDiscount List:")
        print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Active'}")
        print("-" * 100)

        for discount in discounts:
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            active_status = "Yes" if discount['is_active'] else "No"

            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {active_status}")

        # Get discount to toggle
        discount_id = input("\nEnter discount ID to toggle status: ").strip().upper()

        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )

        discount = cursor.fetchone()

        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return

        # Toggle status
        new_status = 0 if discount['is_active'] else 1
        status_text = "activated" if new_status else "deactivated"

        confirm = input(f"Are you sure you want to {status_text.lower()} '{discount['name']}'? (y/n): ").strip().lower()

        if confirm != 'y':
            print("Operation cancelled.")
            conn.close()
            return

        cursor.execute(
            '''
            UPDATE shop_discounts
            SET is_active = ?
            WHERE discount_id = ?
            ''',
            [new_status, discount_id]
        )

        conn.commit()

        print(f"\nDiscount {discount_id} - '{discount['name']}' has been {status_text}.")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error toggling discount status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error toggling discount status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


@log_read(module="shop", description="Viewing all discounts")
def view_all_discounts():
    """View all discounts in the system"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view discounts.")
        return

    if not config.auth.check_permission('manage_discounts'):
        print("You don't have permission to view discounts.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all discounts
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, end_date, start_date
            '''
        )

        discounts = cursor.fetchall()

        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return

        # Check for active vs inactive, current vs expired
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        active_current = []
        active_future = []
        active_expired = []
        inactive = []

        for discount in discounts:
            if discount['is_active']:
                if discount['end_date'] and discount['end_date'] < now:
                    active_expired.append(discount)
                elif discount['start_date'] > now:
                    active_future.append(discount)
                else:
                    active_current.append(discount)
            else:
                inactive.append(discount)

        # Display discounts by category
        def print_discount_header():
            print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Min Purchase':<15}")
            print("-" * 110)

        def print_discount(discount):
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            min_purchase = f"£{discount['min_purchase_amount']:.2f}" if discount['min_purchase_amount'] > 0 else 'None'

            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {min_purchase:<15}")

        # Active and current
        if active_current:
            print("\n=== Active & Current Discounts ===")
            print_discount_header()
            for discount in active_current:
                print_discount(discount)

        # Active but future
        if active_future:
            print("\n=== Active & Future Discounts ===")
            print_discount_header()
            for discount in active_future:
                print_discount(discount)

        # Active but expired
        if active_expired:
            print("\n=== Active but Expired Discounts ===")
            print_discount_header()
            for discount in active_expired:
                print_discount(discount)

        # Inactive
        if inactive:
            print("\n=== Inactive Discounts ===")
            print_discount_header()
            for discount in inactive:
                print_discount(discount)

        # Display summary
        print(f"\nTotal Discounts: {len(discounts)}")
        print(f"Active & Current: {len(active_current)}")
        print(f"Active & Future: {len(active_future)}")
        print(f"Active but Expired: {len(active_expired)}")
        print(f"Inactive: {len(inactive)}")

        # View discount details option
        discount_id = input("\nEnter discount ID to view details (or 'back' to return): ").strip().upper()

        if discount_id.lower() == 'back':
            conn.close()
            return

        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )

        discount = cursor.fetchone()

        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return

        # Display full discount details
        print(f"\nDiscount Details - {discount_id}")
        print(f"Name: {discount['name']}")
        print(f"Description: {discount['description']}")
        print(f"Type: {discount['discount_type']}")
        value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
        print(f"Value: {value_display}")
        print(f"Start Date: {discount['start_date']}")
        print(f"End Date: {discount['end_date'] if discount['end_date'] else 'Never'}")
        print(f"Status: {'Active' if discount['is_active'] else 'Inactive'}")

        if discount['applicable_products'] == 'all':
            print("Applies to: All products")
        else:
            if ',' in discount['applicable_products']:
                product_ids = discount['applicable_products'].split(',')
                print(f"Applies to: {len(product_ids)} specific products")

                # Get product details
                placeholders = ','.join(['?'] * len(product_ids))
                cursor.execute(
                    f"SELECT source_product_id as product_id, name FROM products WHERE source_type = 'shop' AND source_product_id IN ({placeholders})",
                    product_ids
                )
                products = cursor.fetchall()

                if products:
                    print("\nApplicable Products:")
                    for product in products:
                        print(f"- {product['product_id']}: {product['name']}")
            else:
                # Assume it's a category
                print(f"Applies to Category: {discount['applicable_products']}")

                # Count products in this category
                cursor.execute(
                    "SELECT COUNT(*) FROM products WHERE source_type = 'shop' AND category = ? AND is_active = 1",
                    [discount['applicable_products']]
                )
                count = cursor.fetchone()[0]
                print(f"({count} active products in this category)")

        print(f"Minimum Purchase: £{discount['min_purchase_amount']:.2f}")
        print(f"Created At: {discount['created_at']}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error viewing discounts: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing discounts: {e}")
        if 'conn' in locals():
            conn.close()


def calculate_discount_for_transaction(cart_items, user_id=None):
    """Calculate applicable discounts for a transaction"""

    if not cart_items:
        return 0, None

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get current active discounts
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE is_active = 1
            AND (start_date IS NULL OR start_date <= ?)
            AND (end_date IS NULL OR end_date >= ?)
            ORDER BY discount_value DESC
            ''',
            [now, now]
        )

        discounts = cursor.fetchall()

        if not discounts:
            conn.close()
            return 0, None

        # Calculate subtotal
        subtotal = sum(item['price'] * item['quantity'] for item in cart_items)

        best_discount = None
        best_discount_amount = 0

        for discount in discounts:
            # Check minimum purchase amount
            if discount['min_purchase_amount'] > subtotal:
                continue

            # Check applicable products
            applicable = False

            if discount['applicable_products'] == 'all':
                applicable = True
            else:
                # Check if any cart items match the discount criteria
                if ',' in discount['applicable_products']:
                    # Specific product list
                    applicable_products = discount['applicable_products'].split(',')
                    applicable = any(item['product_id'] in applicable_products for item in cart_items)
                else:
                    # Category
                    applicable = any(item.get('category') == discount['applicable_products'] for item in cart_items)

            if not applicable:
                continue

            # Calculate discount amount
            if discount['discount_type'] == 'percentage':
                discount_amount = subtotal * (discount['discount_value'] / 100)
            else:  # fixed
                discount_amount = discount['discount_value']

            # Don't let discount exceed subtotal
            discount_amount = min(discount_amount, subtotal)

            if discount_amount > best_discount_amount:
                best_discount_amount = discount_amount
                best_discount = discount

        conn.close()
        return best_discount_amount, best_discount

    except Exception as e:
        print(f"Error calculating discount: {e}")
        if 'conn' in locals():
            conn.close()
        return 0, None


def cleanup_expired_discounts():
    """Clean up expired discounts from the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Deactivate expired discounts
        cursor.execute(
            '''
            UPDATE shop_discounts
            SET is_active = 0
            WHERE end_date IS NOT NULL AND end_date < ? AND is_active = 1
            ''',
            [now]
        )

        expired_count = cursor.rowcount
        conn.commit()
        conn.close()

        if expired_count > 0:
            print(f"Deactivated {expired_count} expired discount(s).")

        return expired_count

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error cleaning up expired discounts: {e}")
        return 0
