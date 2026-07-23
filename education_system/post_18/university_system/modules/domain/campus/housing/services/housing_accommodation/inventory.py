from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create,
)


# Inventory Management
@log_create(module="housing", description="Managing room inventory")
def manage_inventory():
    """Manage room inventory"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to manage inventory.")
        return

    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to manage inventory.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nInventory Management:")
        print("1. Add Inventory Item")
        print("2. View Room Inventory")
        print("3. Update Item Condition")
        print("4. Remove Item")
        print("5. Return to Housing Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '5':
            conn.close()
            return

        # For all options except returning, we need to select a room
        if choice in ['1', '2', '3', '4']:
            print("\nSelect Building:")

            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()

            if not buildings:
                print("No buildings found in the system.")
                conn.close()
                return

            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")

            while True:
                try:
                    bchoice = int(input("\nSelect building (enter number): "))
                    if 1 <= bchoice <= len(buildings):
                        building_id = buildings[bchoice - 1][0]
                        building_name = buildings[bchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")

            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))

            rooms = cursor.fetchall()

            if not rooms:
                print(f"No rooms found in {building_name}.")
                conn.close()
                return

            print(f"\nSelect Room in {building_name}:")
            for i, room in enumerate(rooms, 1):
                print(f"{i}. Room {room[1]} (Floor {room[2]}, {room[3]})")

            while True:
                try:
                    rchoice = int(input("\nSelect room (enter number): "))
                    if 1 <= rchoice <= len(rooms):
                        room_id = rooms[rchoice - 1][0]
                        room_number = rooms[rchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(rooms)}.")
                except ValueError:
                    print("Please enter a valid number.")

        # Process the selected choice
        if choice == '1':
            # Add inventory item
            print(f"\nAdding Inventory Item to Room {room_number} in {building_name}")

            item_name = input("Item Name: ").strip()
            if not item_name:
                print("Item name cannot be empty.")
                conn.close()
                return

            print("\nSelect Item Type:")
            item_types = ["Furniture", "Appliance", "Electronic", "Kitchen", "Bathroom", "Decor", "Safety", "Other"]

            for i, itype in enumerate(item_types, 1):
                print(f"{i}. {itype}")

            while True:
                try:
                    tchoice = int(input("\nSelect item type (enter number): "))
                    if 1 <= tchoice <= len(item_types):
                        item_type = item_types[tchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(item_types)}.")
                except ValueError:
                    print("Please enter a valid number.")

            print("\nSelect Condition:")
            conditions = ["New", "Excellent", "Good", "Fair", "Poor", "Damaged"]

            for i, cond in enumerate(conditions, 1):
                print(f"{i}. {cond}")

            while True:
                try:
                    cchoice = int(input("\nSelect condition (enter number): "))
                    if 1 <= cchoice <= len(conditions):
                        condition = conditions[cchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(conditions)}.")
                except ValueError:
                    print("Please enter a valid number.")

            acquisition_date = input("Acquisition Date (YYYY-MM-DD, leave blank for today): ").strip()
            if not acquisition_date:
                acquisition_date = datetime.datetime.now().strftime('%Y-%m-%d')
            else:
                try:
                    # Validate date format
                    datetime.datetime.strptime(acquisition_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Using today's date instead.")
                    acquisition_date = datetime.datetime.now().strftime('%Y-%m-%d')

            notes = input("Additional Notes: ").strip() or None

            # Create inventory item
            item_id = generate_id('INV')
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO housing_inventory (
                item_id, room_id, item_name, item_type, condition, acquisition_date,
                status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_id, room_id, item_name, item_type, condition, acquisition_date,
                'In Room', notes, timestamp, timestamp
            ))

            conn.commit()
            print(f"\nInventory item '{item_name}' added successfully with ID: {item_id}")

        elif choice == '2':
            # View room inventory
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition, acquisition_date, status, notes
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))

            items = cursor.fetchall()

            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return

            print(f"\nInventory for Room {room_number} in {building_name}:")
            print("=" * 80)
            print(f"{'Item':<20} {'Type':<15} {'Condition':<10} {'Acquired':<12} {'Status':<12}")
            print("-" * 80)

            for item in items:
                print(f"{item[1]:<20} {item[2]:<15} {item[3]:<10} {item[4]:<12} {item[5]:<12}")
                if item[6]:
                    print(f"   Notes: {item[6]}")

            print("=" * 80)

        elif choice == '3':
            # Update item condition
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))

            items = cursor.fetchall()

            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return

            print("\nSelect Item to Update Condition:")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item[1]} ({item[2]}) - Current Condition: {item[3]}")

            while True:
                try:
                    ichoice = int(input("\nSelect item (enter number): "))
                    if 1 <= ichoice <= len(items):
                        item_id = items[ichoice - 1][0]
                        item_name = items[ichoice - 1][1]
                        current_condition = items[ichoice - 1][3]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(items)}.")
                except ValueError:
                    print("Please enter a valid number.")

            print(f"\nCurrent Condition: {current_condition}")
            print("\nSelect New Condition:")
            conditions = ["New", "Excellent", "Good", "Fair", "Poor", "Damaged"]

            for i, cond in enumerate(conditions, 1):
                print(f"{i}. {cond}")

            while True:
                try:
                    cchoice = int(input("\nSelect condition (enter number): "))
                    if 1 <= cchoice <= len(conditions):
                        new_condition = conditions[cchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(conditions)}.")
                except ValueError:
                    print("Please enter a valid number.")

            notes = input("Additional Notes: ").strip() or None
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE housing_inventory
            SET condition = ?, notes = ?, updated_at = ?
            WHERE item_id = ?
            ''', (new_condition, notes, timestamp, item_id))

            conn.commit()
            print(f"\nCondition for '{item_name}' updated from '{current_condition}' to '{new_condition}'")

        elif choice == '4':
            # Remove item
            cursor.execute('''
            SELECT item_id, item_name, item_type, condition
            FROM housing_inventory
            WHERE room_id = ?
            ORDER BY item_type, item_name
            ''', (room_id,))

            items = cursor.fetchall()

            if not items:
                print(f"\nNo inventory items found for Room {room_number} in {building_name}.")
                conn.close()
                return

            print("\nSelect Item to Remove:")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item[1]} ({item[2]}) - Condition: {item[3]}")

            while True:
                try:
                    ichoice = int(input("\nSelect item (enter number): "))
                    if 1 <= ichoice <= len(items):
                        item_id = items[ichoice - 1][0]
                        item_name = items[ichoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(items)}.")
                except ValueError:
                    print("Please enter a valid number.")

            print("\nRemoval Reason:")
            print("1. Damaged Beyond Repair")
            print("2. Replaced")
            print("3. Moved to Another Room")
            print("4. Lost/Stolen")
            print("5. Other")

            reason_choice = input("\nSelect reason (1-5): ")
            reason_map = {
                '1': 'Damaged Beyond Repair',
                '2': 'Replaced',
                '3': 'Moved to Another Room',
                '4': 'Lost/Stolen',
                '5': 'Other'
            }

            if reason_choice in reason_map:
                reason = reason_map[reason_choice]
            else:
                reason = "Other"

            additional_notes = input("Additional Notes: ").strip() or None

            confirm = input(f"\nAre you sure you want to remove '{item_name}'? (y/n): ").lower()

            if confirm == 'y':
                # Option to mark as removed instead of deleting
                mark_choice = input("Mark as removed (r) or permanently delete (d)? (r/d): ").lower()

                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if mark_choice == 'd':
                    # Delete completely
                    cursor.execute('DELETE FROM housing_inventory WHERE item_id = ?', (item_id,))
                    print(f"\nItem '{item_name}' has been permanently deleted.")
                else:
                    # Mark as removed
                    notes_with_reason = f"Removed: {reason}"
                    if additional_notes:
                        notes_with_reason += f" - {additional_notes}"

                    cursor.execute('''
                    UPDATE housing_inventory
                    SET status = 'Removed', notes = ?, updated_at = ?
                    WHERE item_id = ?
                    ''', (notes_with_reason, timestamp, item_id))

                    print(f"\nItem '{item_name}' marked as removed with reason: {reason}")

                conn.commit()
            else:
                print("Removal cancelled.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error managing inventory: {e}")
