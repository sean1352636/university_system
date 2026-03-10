import logging
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.utils.logging.log_config import configure_logging
from .constants import VEHICLE_TYPES
from . import core

_t = get_text
logger = configure_logging(name=__name__)


def register_vehicle():
    auth = core.auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to register vehicle")
        print(_t("parking.auth.login_required"))
        return

    if not (auth.check_permission('register_vehicle') or auth.check_permission('register_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to register vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Determine owner ID based on role
        owner_id = None

        if auth.check_permission('register_vehicle'):
            # Admin/staff can register for any user
            print("\n" + _t("parking.section.register_vehicle_for") + ":")
            print("1. " + _t("parking.menu.self"))
            print("2. " + _t("parking.menu.another_user"))

            choice = input("Enter your choice (1-2): ")

            if choice == '1':
                owner_id = auth.current_user['id']
            elif choice == '2':
                search_term = input("Enter user ID, username, or email to search: ")
                cursor.execute('''
                SELECT id, first_name, last_name, email FROM users
                WHERE id = ? OR username = ? OR email = ?
                ''', (search_term, search_term, search_term))

                user = cursor.fetchone()
                if not user:
                    print(_t("parking.error.user_not_found"))
                    conn.close()
                    return

                owner_id = user[0]
                print(f"Registering vehicle for: {user[1]} {user[2]} ({user[0]})")
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return
        else:
            # Regular users can only register for themselves
            owner_id = auth.current_user['id']

        # Get vehicle details
        try:
            license_plate = input("Enter license plate: ").upper()
            if not license_plate:
                print(_t("parking.error.license_plate_required"))
                conn.close()
                return

            # Check if license plate already exists
            cursor.execute('SELECT COUNT(*) FROM vehicles WHERE license_plate = ?', (license_plate,))
            if cursor.fetchone()[0] > 0:
                print(_t("parking.error.license_plate_exists"))
                conn.close()
                return

            make = input("Enter vehicle make: ")
            if not make:
                print(_t("parking.error.make_required"))
                conn.close()
                return

            model = input("Enter vehicle model: ")
            if not model:
                print(_t("parking.error.model_required"))
                conn.close()
                return

            # Ask for vehicle year with validation
            year = None
            while not year:
                try:
                    year_input = input("Enter vehicle year (YYYY): ")
                    year = int(year_input)
                    current_year = datetime.now().year
                    if year < 1900 or year > current_year + 1:
                        print(_t("parking.error.year_range").format(max_year=current_year + 1))
                        year = None
                except ValueError:
                    print(_t("parking.error.year_must_be_number"))

            color = input("Enter vehicle color: ")

            # Ask for vehicle type with validation
            print(_t("parking.vehicle.types_available") + ":", ", ".join(VEHICLE_TYPES))
            while True:
                vehicle_type = input("Enter vehicle type: ")
                if not vehicle_type:
                    vehicle_type = "Sedan"  # Default
                    break
                if vehicle_type in VEHICLE_TYPES:
                    break
                print(f"Invalid vehicle type. Please choose from {', '.join(VEHICLE_TYPES)}")

            registration_state = input("Enter registration state (e.g., NY): ").upper()
            if not registration_state:
                print(_t("parking.error.registration_state_required"))
                conn.close()
                return

            # Generate vehicle ID
            cursor.execute('SELECT COUNT(*) FROM vehicles')
            count = cursor.fetchone()[0] + 1
            vehicle_id = f"V{str(count).zfill(6)}"

            # Insert vehicle
            cursor.execute(
                'INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (vehicle_id, license_plate, make, model, year, color, vehicle_type, owner_id, registration_state)
            )

            conn.commit()

            print(f"\nVehicle registered successfully!")
            print(f"Vehicle ID: {vehicle_id}")
            print(f"License Plate: {license_plate}")
            print(f"Make/Model: {make} {model}")
            print(f"Year: {year}")
            print(f"Color: {color}")
            print(f"Type: {vehicle_type}")
            print(f"Registration State: {registration_state}")

            logging.info(f"Vehicle {vehicle_id} registered for user {owner_id}")

        except Exception as e:
            logging.error(f"Error registering vehicle: {e}")
            print(_t("parking.error.registering_vehicle") + f": {e}")
            conn.rollback()

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in register_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in register_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def view_vehicle():
    auth = core.auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to view vehicles")
        print(_t("parking.auth.login_required"))
        return

    if not (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to view vehicles without permission")
        print(_t("parking.auth.no_permission"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if auth.check_permission('view_any_vehicle'):
            # Admin or staff - can view any vehicle
            print("\n" + _t("parking.section.view_vehicles") + ":")
            print("1. " + _t("parking.menu.view_all_vehicles"))
            print("2. " + _t("parking.menu.search_by_vehicle_id"))
            print("3. " + _t("parking.menu.search_by_license_plate"))
            print("4. " + _t("parking.menu.search_by_owner_id"))

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                # View all vehicles
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                ORDER BY v.vehicle_id
                ''')

                vehicles = cursor.fetchall()

                if not vehicles:
                    print(_t("parking.msg.no_vehicles_found"))
                    conn.close()
                    return

                print("\n" + _t("parking.section.all_vehicles") + ":")
                print("=" * 100)
                for vehicle in vehicles:
                    display_vehicle_details(vehicle)
                    print("-" * 100)

            elif choice == '2':
                # Search by vehicle ID
                vehicle_id = input("Enter vehicle ID: ")
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.vehicle_id = ?
                ''', (vehicle_id,))

                vehicle = cursor.fetchone()

                if not vehicle:
                    print(f"No vehicle found with ID: {vehicle_id}")
                else:
                    display_vehicle_details(vehicle)

            elif choice == '3':
                # Search by license plate
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.license_plate = ?
                ''', (license_plate,))

                vehicle = cursor.fetchone()

                if not vehicle:
                    print(f"No vehicle found with license plate: {license_plate}")
                else:
                    display_vehicle_details(vehicle)

            elif choice == '4':
                # Search by owner ID
                owner_id = input("Enter owner ID: ")
                cursor.execute('''
                SELECT v.*, u.first_name, u.last_name
                FROM vehicles v
                LEFT JOIN users u ON v.owner_id = u.id
                WHERE v.owner_id = ?
                ORDER BY v.vehicle_id
                ''', (owner_id,))

                vehicles = cursor.fetchall()

                if not vehicles:
                    print(f"No vehicles found for owner ID: {owner_id}")
                else:
                    print(f"\nVehicles for Owner ID: {owner_id}")
                    print("=" * 100)
                    for vehicle in vehicles:
                        display_vehicle_details(vehicle)
                        print("-" * 100)

            else:
                print(_t("common.invalid_choice"))

        elif auth.check_permission('view_own_vehicle'):
            # User - can only view their own vehicles
            owner_id = auth.current_user['id']

            cursor.execute('''
            SELECT v.*, u.first_name, u.last_name
            FROM vehicles v
            LEFT JOIN users u ON v.owner_id = u.id
            WHERE v.owner_id = ?
            ORDER BY v.vehicle_id
            ''', (owner_id,))

            vehicles = cursor.fetchall()

            if not vehicles:
                print(_t("parking.msg.no_your_vehicles"))
            else:
                print("\n" + _t("parking.section.your_vehicles") + ":")
                print("=" * 100)
                for vehicle in vehicles:
                    display_vehicle_details(vehicle)
                    print("-" * 100)

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in view_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in view_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def update_vehicle():
    auth = core.auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to update vehicle")
        print(_t("parking.auth.login_required"))
        return

    if not (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to update vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return

    # Backup before making changes
    backup_before_operation('update_vehicle')

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()

        # Identify vehicle to update
        if auth.check_permission('update_any_vehicle'):
            # Admin/staff can update any vehicle
            print("\n" + _t("parking.section.search_vehicle_update") + ":")
            print("1. " + _t("parking.menu.search_by_vehicle_id"))
            print("2. " + _t("parking.menu.search_by_license_plate"))

            choice = input("Enter your choice (1-2): ")

            vehicle = None

            if choice == '1':
                vehicle_id = input("Enter vehicle ID: ")
                cursor.execute('SELECT * FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
                vehicle = cursor.fetchone()

            elif choice == '2':
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('SELECT * FROM vehicles WHERE license_plate = ?', (license_plate,))
                vehicle = cursor.fetchone()

            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return

            if not vehicle:
                print(_t("parking.msg.no_vehicle_criteria"))
                conn.close()
                return

        else:
            # Regular user can only update their own vehicles
            owner_id = auth.current_user['id']

            cursor.execute('SELECT * FROM vehicles WHERE owner_id = ?', (owner_id,))

            vehicles = cursor.fetchall()

            if not vehicles:
                print(_t("parking.msg.no_vehicles_to_update"))
                conn.close()
                return

            # Let user choose which vehicle to update
            print("\n" + _t("parking.section.your_vehicles") + ":")
            for i, v in enumerate(vehicles):
                print(f"{i+1}. {v['license_plate']} - {v['make']} {v['model']}")

            try:
                idx = int(input("Select a vehicle to update (number): ")) - 1
                if idx < 0 or idx >= len(vehicles):
                    raise ValueError
                vehicle = vehicles[idx]
            except (ValueError, IndexError):
                print(_t("common.invalid_selection"))
                conn.close()
                return

        # Display current vehicle details
        print("\n" + _t("parking.section.current_vehicle_details") + ":")
        print(f"Vehicle ID: {vehicle['vehicle_id']}")
        print(f"License Plate: {vehicle['license_plate']}")
        print(f"Make: {vehicle['make']}")
        print(f"Model: {vehicle['model']}")
        print(f"Year: {vehicle['year']}")
        print(f"Color: {vehicle['color']}")
        print(f"Type: {vehicle['vehicle_type']}")
        print(f"Registration State: {vehicle['registration_state']}")

        # Ask what field to update
        print("\n" + _t("parking.section.what_to_update") + "?")
        print("1. " + _t("parking.menu.license_plate"))
        print("2. " + _t("parking.menu.make"))
        print("3. " + _t("parking.menu.model"))
        print("4. " + _t("parking.menu.year"))
        print("5. " + _t("parking.menu.color"))
        print("6. " + _t("parking.menu.vehicle_type"))
        print("7. " + _t("parking.menu.registration_state"))

        if auth.check_permission('update_any_vehicle'):
            print("8. " + _t("parking.menu.owner"))
            max_option = 8
        else:
            max_option = 7

        try:
            option = int(input(f"Enter your choice (1-{max_option}): "))
            if option < 1 or option > max_option:
                raise ValueError
        except ValueError:
            print(_t("common.invalid_option"))
            conn.close()
            return

        # Update based on selection
        if option == 1:
            # Update license plate
            new_plate = input("Enter new license plate: ").upper()
            if not new_plate:
                print(_t("parking.error.license_plate_empty"))
                conn.close()
                return

            # Check if the new plate already exists (and is not this vehicle)
            cursor.execute(
                'SELECT COUNT(*) FROM vehicles WHERE license_plate = ? AND vehicle_id != ?',
                (new_plate, vehicle['vehicle_id'])
            )
            if cursor.fetchone()[0] > 0:
                print(_t("parking.error.license_plate_other_vehicle"))
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET license_plate = ? WHERE vehicle_id = ?',
                (new_plate, vehicle['vehicle_id'])
            )

            # Also update any violations that reference this license plate
            cursor.execute(
                'UPDATE parking_violations SET license_plate = ? WHERE vehicle_id = ?',
                (new_plate, vehicle['vehicle_id'])
            )

            print(f"License plate updated to: {new_plate}")

        elif option == 2:
            # Update make
            new_make = input("Enter new make: ")
            if not new_make:
                print(_t("parking.error.make_empty"))
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET make = ? WHERE vehicle_id = ?',
                (new_make, vehicle['vehicle_id'])
            )

            print(f"Make updated to: {new_make}")

        elif option == 3:
            # Update model
            new_model = input("Enter new model: ")
            if not new_model:
                print(_t("parking.error.model_empty"))
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET model = ? WHERE vehicle_id = ?',
                (new_model, vehicle['vehicle_id'])
            )

            print(f"Model updated to: {new_model}")

        elif option == 4:
            # Update year
            try:
                new_year = int(input("Enter new year: "))
                current_year = datetime.now().year
                if new_year < 1900 or new_year > current_year + 1:
                    print(_t("parking.error.year_range").format(max_year=current_year + 1))
                    conn.close()
                    return

                cursor.execute(
                    'UPDATE vehicles SET year = ? WHERE vehicle_id = ?',
                    (new_year, vehicle['vehicle_id'])
                )

                print(f"Year updated to: {new_year}")

            except ValueError:
                print(_t("parking.error.year_must_be_number"))
                conn.close()
                return

        elif option == 5:
            # Update color
            new_color = input("Enter new color: ")
            if not new_color:
                print(_t("parking.error.color_empty"))
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET color = ? WHERE vehicle_id = ?',
                (new_color, vehicle['vehicle_id'])
            )

            print(f"Color updated to: {new_color}")

        elif option == 6:
            # Update vehicle type
            print(_t("parking.vehicle.types_available") + ":", ", ".join(VEHICLE_TYPES))
            while True:
                new_type = input("Enter new vehicle type: ")
                if not new_type:
                    new_type = "Sedan"  # Default
                    break
                if new_type in VEHICLE_TYPES:
                    break
                print(f"Invalid vehicle type. Please choose from {', '.join(VEHICLE_TYPES)}")

            cursor.execute(
                'UPDATE vehicles SET vehicle_type = ? WHERE vehicle_id = ?',
                (new_type, vehicle['vehicle_id'])
            )

            print(f"Vehicle type updated to: {new_type}")

        elif option == 7:
            # Update registration state
            new_state = input("Enter new registration state: ").upper()
            if not new_state:
                print(_t("parking.error.registration_state_empty"))
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET registration_state = ? WHERE vehicle_id = ?',
                (new_state, vehicle['vehicle_id'])
            )

            print(f"Registration state updated to: {new_state}")

        elif option == 8 and auth.check_permission('update_any_vehicle'):
            # Update owner (admin only)
            new_owner_id = input("Enter new owner ID: ")

            # Verify owner exists
            cursor.execute('SELECT id FROM users WHERE id = ?', (new_owner_id,))
            if not cursor.fetchone():
                print(f"Error: User with ID {new_owner_id} does not exist.")
                conn.close()
                return

            cursor.execute(
                'UPDATE vehicles SET owner_id = ? WHERE vehicle_id = ?',
                (new_owner_id, vehicle['vehicle_id'])
            )

            print(f"Owner updated to ID: {new_owner_id}")

        # Commit changes
        conn.commit()

        # Display updated vehicle
        cursor.execute('''
        SELECT v.*, u.first_name, u.last_name
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        WHERE v.vehicle_id = ?
        ''', (vehicle['vehicle_id'],))

        updated_vehicle = cursor.fetchone()

        print("\n" + _t("parking.msg.vehicle_updated") + "!")
        print("\n" + _t("parking.section.updated_vehicle_details") + ":")
        display_vehicle_details(updated_vehicle)

        logging.info(f"Vehicle {vehicle['vehicle_id']} updated by {auth.current_user['username']}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in update_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def delete_vehicle():
    auth = core.auth

    # Check for permission
    if not auth or not auth.current_user:
        logging.warning("Unauthorized attempt to delete vehicle")
        print(_t("parking.auth.login_required"))
        return

    if not (auth.check_permission('delete_any_vehicle') or auth.check_permission('delete_own_vehicle')):
        logging.warning(f"User {auth.current_user['username']} attempted to delete vehicle without permission")
        print(_t("parking.auth.no_permission"))
        return

    # Backup before making changes
    backup_before_operation('delete_vehicle')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        vehicle_id = None

        if auth.check_permission('delete_any_vehicle'):
            # Admin/staff can delete any vehicle
            print("\n" + _t("parking.section.search_vehicle_delete") + ":")
            print("1. " + _t("parking.menu.by_vehicle_id"))
            print("2. " + _t("parking.menu.by_license_plate"))

            choice = input("Enter your choice (1-2): ")

            if choice == '1':
                vehicle_id = input("Enter vehicle ID: ")
            elif choice == '2':
                license_plate = input("Enter license plate: ").upper()
                cursor.execute('SELECT vehicle_id FROM vehicles WHERE license_plate = ?', (license_plate,))
                result = cursor.fetchone()
                if result:
                    vehicle_id = result[0]
                else:
                    print(f"No vehicle found with license plate: {license_plate}")
                    conn.close()
                    return
            else:
                print(_t("common.invalid_choice"))
                conn.close()
                return

        else:
            # Regular user can only delete their own vehicles
            owner_id = auth.current_user['id']

            cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles WHERE owner_id = ?', (owner_id,))

            vehicles = cursor.fetchall()

            if not vehicles:
                print(_t("parking.msg.no_vehicles_to_delete"))
                conn.close()
                return

            # Let user choose which vehicle to delete
            print("\n" + _t("parking.section.your_vehicles") + ":")
            for i, v in enumerate(vehicles):
                print(f"{i+1}. {v[1]} - {v[2]} {v[3]}")

            try:
                idx = int(input("Select a vehicle to delete (number): ")) - 1
                if idx < 0 or idx >= len(vehicles):
                    raise ValueError
                vehicle_id = vehicles[idx][0]
            except (ValueError, IndexError):
                print(_t("common.invalid_selection"))
                conn.close()
                return

        # Check if vehicle exists
        cursor.execute('''
        SELECT v.*, u.first_name, u.last_name
        FROM vehicles v
        LEFT JOIN users u ON v.owner_id = u.id
        WHERE v.vehicle_id = ?
        ''', (vehicle_id,))

        vehicle = cursor.fetchone()

        if not vehicle:
            print(f"No vehicle found with ID: {vehicle_id}")
            conn.close()
            return

        # Check if the vehicle is associated with any active permits
        cursor.execute('''
        SELECT permit_id FROM parking_permits
        WHERE vehicle_id = ? AND active_status = 'Active'
        ''', (vehicle_id,))

        active_permits = cursor.fetchall()

        if active_permits:
            permit_ids = ", ".join([p[0] for p in active_permits])
            print(f"Error: Vehicle is associated with active permits: {permit_ids}")
            print(_t("parking.msg.delete_permits_first"))
            conn.close()
            return

        # Display vehicle details and confirm deletion
        print("\n" + _t("parking.section.vehicle_details") + ":")
        print(f"Vehicle ID: {vehicle[0]}")
        print(f"License Plate: {vehicle[1]}")
        print(f"Make/Model: {vehicle[2]} {vehicle[3]}")
        print(f"Year: {vehicle[4]}")
        print(f"Owner: {vehicle[9]} {vehicle[10]}")

        confirm = input("\nAre you sure you want to delete this vehicle? (y/n): ")

        if confirm.lower() != 'y':
            print(_t("common.deletion_cancelled"))
            conn.close()
            return

        # Update any permits to remove this vehicle
        cursor.execute(
            'UPDATE parking_permits SET vehicle_id = NULL WHERE vehicle_id = ?',
            (vehicle_id,)
        )

        # Delete the vehicle
        cursor.execute('DELETE FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))

        conn.commit()
        print(f"Vehicle {vehicle_id} has been deleted successfully.")
        logging.info(f"Vehicle {vehicle_id} deleted by {auth.current_user['username']}")

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in delete_vehicle: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in delete_vehicle: {e}")
        print(f"An unexpected error occurred: {e}")


def display_vehicle_details(vehicle):
    """Display the details of a vehicle"""
    print(f"Vehicle ID: {vehicle[0]}")
    print(f"License Plate: {vehicle[1]}")
    print(f"Make/Model: {vehicle[2]} {vehicle[3]}")
    print(f"Year: {vehicle[4]}")
    print(f"Color: {vehicle[5]}")
    print(f"Type: {vehicle[6]}")
    print(f"Registration State: {vehicle[8]}")

    # Check if owner info is available (from join)
    if len(vehicle) > 9 and vehicle[9] and vehicle[10]:
        print(f"Owner: {vehicle[9]} {vehicle[10]} ({vehicle[7]})")
    else:
        print(f"Owner ID: {vehicle[7]}")
