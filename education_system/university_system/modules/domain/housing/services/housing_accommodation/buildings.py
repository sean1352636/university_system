from education_system.university_system.modules.domain.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    log_create, log_read, log_update, log_delete,
)

# Building Management Functions
@log_create(module="housing", description="Creating new building")
def create_building():
    """Create a new housing building"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.building.create")))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.building.create")))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + get_text("housing.building.create_title"))
        print("=" * 27)

        # Get building details
        building_id = generate_id('BLD')

        building_name = input(get_text("housing.building.enter_name") + ": ").strip()
        if not building_name:
            print(get_text("housing.building.error_name_empty"))
            conn.close()
            return

        address = input(get_text("housing.building.enter_address") + ": ").strip()
        if not address:
            print(get_text("housing.building.error_address_empty"))
            conn.close()
            return

        campus_location = input(get_text("housing.building.enter_campus") + ": ").strip()
        if not campus_location:
            print(get_text("housing.building.error_campus_empty"))
            conn.close()
            return

        while True:
            try:
                total_rooms = int(input(get_text("housing.building.enter_total_rooms") + ": "))
                if total_rooms <= 0:
                    print(get_text("housing.building.error_rooms_positive"))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        while True:
            try:
                available_rooms = int(input(get_text("housing.building.enter_available") + ": "))
                if available_rooms < 0 or available_rooms > total_rooms:
                    print(get_text("housing.building.error_available_range", total=total_rooms))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        has_elevator = input(get_text("housing.building.has_elevator") + " " + get_text("common.yes_no_prompt") + ": ").lower() == get_text("common.yes")
        has_accessible_rooms = input(get_text("housing.building.has_accessible") + " " + get_text("common.yes_no_prompt") + ": ").lower() == get_text("common.yes")
        has_kitchen = input(get_text("housing.building.has_kitchen") + " " + get_text("common.yes_no_prompt") + ": ").lower() == get_text("common.yes")
        has_laundry = input(get_text("housing.building.has_laundry") + " " + get_text("common.yes_no_prompt") + ": ").lower() == get_text("common.yes")

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert building record
        cursor.execute('''
        INSERT INTO housing_buildings (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            building_id, building_name, address, campus_location, total_rooms, available_rooms,
            1 if has_elevator else 0, 1 if has_accessible_rooms else 0,
            1 if has_kitchen else 0, 1 if has_laundry else 0,
            timestamp, timestamp
        ))

        conn.commit()
        print("\n" + get_text("housing.building.create_success", name=building_name, id=building_id))

        # Ask if user wants to add rooms now
        add_rooms = input("\n" + get_text("housing.building.add_rooms_prompt") + " " + get_text("common.yes_no_prompt") + ": ").lower() == get_text("common.yes")

        if add_rooms:
            create_rooms_for_building(building_id, building_name)

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.building.error_creating", error=str(e)))

@log_create(module="housing", description="Creating new rooms")
def create_rooms_for_building(building_id=None, building_name=None):
    """Create new rooms for a housing building"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.room.create")))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.room.create")))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # If building_id not provided, get it from user
        if building_id is None:
            print("\n" + get_text("housing.building.select") + ":")
            print("=" * 16)

            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()

            if not buildings:
                print(get_text("housing.building.no_buildings"))
                conn.close()
                return

            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")

            while True:
                try:
                    choice = int(input("\n" + get_text("housing.building.select") + ": "))
                    if 1 <= choice <= len(buildings):
                        building_id = buildings[choice - 1][0]
                        building_name = buildings[choice - 1][1]
                        break
                    else:
                        print(get_text("housing.assignment.enter_range", max=len(buildings)))
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

        print("\n" + get_text("housing.room.adding_title", name=building_name))
        print("=" * 40)

        while True:
            try:
                floor_count = int(input(get_text("housing.room.floor_count_prompt") + " "))
                if floor_count <= 0:
                    print(get_text("housing.room.error_floor_positive"))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        for floor in range(1, floor_count + 1):
            print(f"\n" + get_text("housing.room.room_count_prompt", floor=floor).replace("?", ":"))

            while True:
                try:
                    room_count = int(input(get_text("housing.room.room_count_prompt", floor=floor) + " "))
                    if room_count <= 0:
                        print(get_text("housing.room.error_rooms_positive"))
                        continue
                    break
                except ValueError:
                    print(get_text("housing.common.error_valid_number"))

            print("\n" + get_text("housing.room.room_types_title") + ":")
            print("1. " + get_text("housing.room.type_single"))
            print("2. " + get_text("housing.room.type_double"))
            print("3. " + get_text("housing.room.type_triple"))
            print("4. " + get_text("housing.room.type_suite"))
            print("5. " + get_text("housing.room.type_studio"))
            print("6. " + get_text("housing.room.type_apartment"))

            # Batch process room creation
            for room_num in range(1, room_count + 1):
                room_number = f"{floor}{str(room_num).zfill(2)}"
                room_id = f"{building_id}-{room_number}"

                print(f"\n" + get_text("housing.room.room_label", number=room_number) + ":")

                while True:
                    try:
                        room_type_choice = int(input(get_text("housing.room.type_prompt") + " "))
                        if 1 <= room_type_choice <= 6:
                            room_types = ['Single', 'Double', 'Triple', 'Suite', 'Studio', 'Apartment']
                            room_type = room_types[room_type_choice - 1]
                            break
                        else:
                            print(get_text("housing.common.error_range", min=1, max=6))
                    except ValueError:
                        print(get_text("housing.common.error_valid_number"))

                while True:
                    try:
                        max_occupants = int(input(get_text("housing.room.max_occupants_prompt", type=room_type) + " "))
                        if max_occupants <= 0:
                            print(get_text("housing.room.error_occupants_positive"))
                            continue
                        break
                    except ValueError:
                        print(get_text("housing.common.error_valid_number"))

                is_accessible = input(get_text("housing.room.accessible_prompt") + " ").lower() == 'y'

                while True:
                    try:
                        monthly_rent = float(input(get_text("housing.room.rent_prompt") + " $"))
                        if monthly_rent <= 0:
                            print(get_text("housing.room.error_rent_positive"))
                            continue
                        break
                    except ValueError:
                        print(get_text("housing.common.error_valid_amount"))

                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert room record
                cursor.execute('''
                INSERT INTO housing_rooms (
                    room_id, building_id, room_number, floor_number, room_type, max_occupants,
                    current_occupants, is_accessible, status, monthly_rent, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    room_id, building_id, room_number, floor, room_type, max_occupants,
                    0, 1 if is_accessible else 0, 'Available', monthly_rent, timestamp, timestamp
                ))

            print("\n" + get_text("housing.room.added_to_floor", count=room_count, floor=floor))

        # Update available rooms count
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE building_id = ? AND status = "Available"', (building_id,))
        available_count = cursor.fetchone()[0]

        cursor.execute('UPDATE housing_buildings SET available_rooms = ? WHERE building_id = ?', (available_count, building_id))

        conn.commit()
        print("\n" + get_text("housing.room.success_added", name=building_name))
        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.room.error_creating", error=str(e)))

@log_read(module="housing", description="Viewing building details")
def view_building():
    """View details of a housing building"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.building.view")))
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.building.view")))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()

        if not buildings:
            print(get_text("housing.building.no_buildings"))
            conn.close()
            return

        print("\n" + get_text("housing.building.select") + ":")
        print("=" * 22)

        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    break
                else:
                    print(get_text("housing.common.error_range", min=1, max=len(buildings)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        # Fetch building details
        cursor.execute('''
        SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
               has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at
        FROM housing_buildings
        WHERE building_id = ?
        ''', (building_id,))

        building = cursor.fetchone()

        if not building:
            print(get_text("housing.building.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.building.details_title") + ":")
        print("=" * 16)
        print(f"{get_text('housing.building.id_label')}: {building[0]}")
        print(f"{get_text('housing.building.name_label')}: {building[1]}")
        print(f"{get_text('housing.building.address_label')}: {building[2]}")
        print(f"{get_text('housing.building.campus_label')}: {building[3]}")
        print(f"{get_text('housing.building.total_rooms_label')}: {building[4]}")
        print(f"{get_text('housing.building.available_rooms_label')}: {building[5]}")
        print(f"{get_text('housing.building.has_elevator')}: {get_text('housing.common.yes') if building[6] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_accessible')}: {get_text('housing.common.yes') if building[7] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_kitchen')}: {get_text('housing.common.yes') if building[8] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_laundry')}: {get_text('housing.common.yes') if building[9] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.created_label')}: {building[10]}")
        print(f"{get_text('housing.building.updated_label')}: {building[11]}")

        # Get room statistics
        cursor.execute('''
        SELECT room_type, COUNT(*), SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END)
        FROM housing_rooms
        WHERE building_id = ?
        GROUP BY room_type
        ''', (building_id,))

        room_stats = cursor.fetchall()

        print("\n" + get_text("housing.room.statistics_title") + ":")
        print("=" * 15)
        print(f"{get_text('housing.room.type_label'):<10} {get_text('housing.building.total_rooms_label'):<10} {get_text('housing.room.status_available'):<10}")
        print("-" * 30)

        for room_type, total, available in room_stats:
            print(f"{room_type:<10} {total:<10} {available:<10}")

        # Ask if user wants to view rooms
        view_rooms = input("\n" + get_text("housing.room.view_prompt") + " (y/n): ").lower() == 'y'

        if view_rooms:
            cursor.execute('''
            SELECT room_id, room_number, floor_number, room_type, max_occupants,
                   current_occupants, is_accessible, status, monthly_rent
            FROM housing_rooms
            WHERE building_id = ?
            ORDER BY floor_number, room_number
            ''', (building_id,))

            rooms = cursor.fetchall()

            print("\n" + get_text("housing.room.room_list_title") + ":")
            print("=" * 17)
            print(f"{get_text('housing.room.number_label'):<8} {get_text('housing.room.floor_label'):<8} {get_text('housing.room.type_label'):<10} {get_text('housing.room.max_occupants_label'):<10} {get_text('housing.room.current_occupants_label'):<10} {get_text('housing.room.accessible_label'):<12} {get_text('housing.room.status_label'):<12} {get_text('housing.room.rent_label'):<8}")
            print("-" * 80)

            for room in rooms:
                print(f"{room[1]:<8} {room[2]:<8} {room[3]:<10} {room[4]:<10} {room[5]:<10} {get_text('housing.common.yes') if room[6] else get_text('housing.common.no'):<12} {room[7]:<12} £{room[8]:<7.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.building.error_viewing", error=str(e)))

@log_update(module="housing", description="Updating building details")
def update_building():
    """Update details of a housing building"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.building.update")))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.building.update")))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()

        if not buildings:
            print(get_text("housing.building.no_buildings"))
            conn.close()
            return

        print("\n" + get_text("housing.building.select") + ":")
        print("=" * 24)

        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    break
                else:
                    print(get_text("housing.common.error_range", min=1, max=len(buildings)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        # Fetch building details
        cursor.execute('''
        SELECT building_name, address, campus_location, total_rooms, available_rooms,
               has_elevator, has_accessible_rooms, has_kitchen, has_laundry
        FROM housing_buildings
        WHERE building_id = ?
        ''', (building_id,))

        building = cursor.fetchone()

        if not building:
            print(get_text("housing.building.not_found"))
            conn.close()
            return

        print("\n" + get_text("housing.building.update_title") + ":")
        print(f"{get_text('housing.building.current_name')}: {building[0]}")
        print(f"{get_text('housing.building.current_address')}: {building[1]}")
        print(f"{get_text('housing.building.current_campus')}: {building[2]}")
        print(f"{get_text('housing.building.current_total_rooms')}: {building[3]}")
        print(f"{get_text('housing.building.current_available_rooms')}: {building[4]}")
        print(f"{get_text('housing.building.has_elevator')}: {get_text('housing.common.yes') if building[5] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_accessible')}: {get_text('housing.common.yes') if building[6] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_kitchen')}: {get_text('housing.common.yes') if building[7] else get_text('housing.common.no')}")
        print(f"{get_text('housing.building.has_laundry')}: {get_text('housing.common.yes') if building[8] else get_text('housing.common.no')}")

        print("\n" + get_text("housing.building.enter_new_values") + ":")

        new_name = input(get_text("housing.building.new_name") + ": ").strip()
        if not new_name:
            new_name = building[0]

        new_address = input(get_text("housing.building.new_address") + ": ").strip()
        if not new_address:
            new_address = building[1]

        new_campus = input(get_text("housing.building.new_campus") + ": ").strip()
        if not new_campus:
            new_campus = building[2]

        new_total_rooms = None
        while True:
            try:
                rooms_input = input(f"{get_text('housing.building.new_total_rooms')} [{building[3]}]: ").strip()
                if not rooms_input:
                    new_total_rooms = building[3]
                    break

                new_total_rooms = int(rooms_input)
                if new_total_rooms <= 0:
                    print(get_text("housing.building.error_rooms_positive"))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        new_available_rooms = None
        while True:
            try:
                rooms_input = input(f"{get_text('housing.building.new_available_rooms')} [{building[4]}]: ").strip()
                if not rooms_input:
                    new_available_rooms = building[4]
                    break

                new_available_rooms = int(rooms_input)
                if new_available_rooms < 0 or new_available_rooms > new_total_rooms:
                    print(get_text("housing.building.error_available_range", total=new_total_rooms))
                    continue
                break
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        has_elevator = input(f"{get_text('housing.building.has_elevator')} (y/n) [{'y' if building[5] else 'n'}]: ").strip().lower()
        if not has_elevator:
            has_elevator = 1 if building[5] else 0
        else:
            has_elevator = 1 if has_elevator == 'y' else 0

        has_accessible = input(f"{get_text('housing.building.has_accessible')} (y/n) [{'y' if building[6] else 'n'}]: ").strip().lower()
        if not has_accessible:
            has_accessible = 1 if building[6] else 0
        else:
            has_accessible = 1 if has_accessible == 'y' else 0

        has_kitchen = input(f"{get_text('housing.building.has_kitchen')} (y/n) [{'y' if building[7] else 'n'}]: ").strip().lower()
        if not has_kitchen:
            has_kitchen = 1 if building[7] else 0
        else:
            has_kitchen = 1 if has_kitchen == 'y' else 0

        has_laundry = input(f"{get_text('housing.building.has_laundry')} (y/n) [{'y' if building[8] else 'n'}]: ").strip().lower()
        if not has_laundry:
            has_laundry = 1 if building[8] else 0
        else:
            has_laundry = 1 if has_laundry == 'y' else 0

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update building record
        cursor.execute('''
        UPDATE housing_buildings
        SET building_name = ?, address = ?, campus_location = ?, total_rooms = ?, available_rooms = ?,
            has_elevator = ?, has_accessible_rooms = ?, has_kitchen = ?, has_laundry = ?, updated_at = ?
        WHERE building_id = ?
        ''', (
            new_name, new_address, new_campus, new_total_rooms, new_available_rooms,
            has_elevator, has_accessible, has_kitchen, has_laundry, timestamp, building_id
        ))

        conn.commit()
        print("\n" + get_text("housing.building.update_success_name", name=new_name))
        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.building.error_updating", error=str(e)))

@log_delete(module="housing", description="Deleting building")
def delete_building():
    """Delete a housing building"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print(get_text("housing.auth.login_required", action=get_text("housing.building.delete")))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.auth.permission_denied", action=get_text("housing.building.delete")))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all buildings
        cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
        buildings = cursor.fetchall()

        if not buildings:
            print(get_text("housing.building.no_buildings"))
            conn.close()
            return

        print("\n" + get_text("housing.building.select") + ":")
        print("=" * 24)

        for i, (bid, bname) in enumerate(buildings, 1):
            print(f"{i}. {bname}")

        while True:
            try:
                choice = int(input("\n" + get_text("housing.common.select_prompt") + " "))
                if 1 <= choice <= len(buildings):
                    building_id = buildings[choice - 1][0]
                    building_name = buildings[choice - 1][1]
                    break
                else:
                    print(get_text("housing.common.error_range", min=1, max=len(buildings)))
            except ValueError:
                print(get_text("housing.common.error_valid_number"))

        # Check for any assigned rooms
        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE building_id = ? AND status != "Available"', (building_id,))
        occupied_count = cursor.fetchone()[0]

        if occupied_count > 0:
            print("\n" + get_text("housing.building.cannot_delete_occupied", name=building_name, count=occupied_count))
            print(get_text("housing.building.reassign_occupants"))
            conn.close()
            return

        # Confirm deletion
        confirm = input("\n" + get_text("housing.building.delete_confirm_rooms", name=building_name) + " (y/n): ").lower()

        if confirm != 'y':
            print(get_text("housing.common.operation_cancelled"))
            conn.close()
            return

        # Delete all rooms in this building
        cursor.execute('DELETE FROM housing_rooms WHERE building_id = ?', (building_id,))

        # Delete the building
        cursor.execute('DELETE FROM housing_buildings WHERE building_id = ?', (building_id,))

        conn.commit()
        print("\n" + get_text("housing.building.delete_success_with_rooms", name=building_name))
        conn.close()

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
    except Exception as e:
        print(get_text("housing.building.error_deleting", error=str(e)))
